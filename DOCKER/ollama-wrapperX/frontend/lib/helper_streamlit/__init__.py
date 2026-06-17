from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from lib.helper_logging import debug
from lib.helper_ollama import helper, Model

import pandas as pd

from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit_antd_components as sac

ICON_INSTALLED = "check-square"
ICON_NOT_INSTALLED = "square"


def models2tree(
    models: list[Model],
    expanded=True,
    with_state=True,
    with_categories=True,
    with_description=True,
    with_sizes=True,
) -> list[sac.TreeItem]:
    items = []

    for model in models:
        name = model.name
        description = model.description
        categories = model.categories

        bool_installed = False
        installed_value = model.installed
        if isinstance(installed_value, bool):
            bool_installed = installed_value
        elif isinstance(installed_value, str):
            bool_installed = (
                installed_value.lower() != "false"
                and installed_value != ICON_NOT_INSTALLED
            )

        installed_icon = ICON_INSTALLED if bool_installed else ICON_NOT_INSTALLED

        tags = []

        if with_categories and categories:
            tags.append(sac.Tag(f"categories: {', '.join(categories)}", color="green"))

        if with_state:
            tags.append(
                sac.Tag(f"installed: {'yes' if bool_installed else 'no'}", color="blue")
            )

        children: list[sac.TreeItem] = []

        sizes = model.sizes
        if with_sizes and sizes:
            for size in sizes:
                try:
                    size_label = size.size
                    size_installed = size.installed
                except:
                    size_label = size['size'] if 'size' in size else '-'
                    size_installed = size['installed'] if 'installed' in size else '-'

                if not size_label:
                    continue

                children.append(
                    sac.TreeItem(
                        label=f"{model.name}:{size_label}",
                        icon=ICON_INSTALLED if size_installed else ICON_NOT_INSTALLED,
                    )
                )

        item_description: str | None = None
        if with_description:
            item_description = description or ""

        item = sac.TreeItem(
            label=name,
            icon=installed_icon,
            description=item_description,
            tag=tags,
            children=children,
        )
        items.append(item)

    return items


def models_view_table(models: Optional[list[Model]] = None) -> None:
    if not models:
        st.write("No models found")
        return

    debug(f"Rendering {len(models)} models in table view")
    normalized = []
    for model in models:
        if isinstance(model, Model):
            normalized.append(model.to_dict())
        else:
            normalized.append(model.name)

    debug(f"Normalized models to {len(normalized)} dicts")
    df = pd.DataFrame(normalized)
    if not df.empty:
        for col in df.columns:
            if df[col].map(lambda v: isinstance(v, datetime)).any():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        def _safe_value(value):
            if isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        df = df.map(_safe_value)

        if df.columns[0] != "Model":
            df.columns = ["Model"] + list(df.columns[1:])

    debug(f"Rendering table with {len(df)} rows and {len(df.columns)} columns")
    st.table(df)
    debug("Rendered table view")


def models_view_tree(
    items: Optional[list[sac.TreeItem]] = None,
    models: Optional[list[Model]] = None,
    expanded=True,
    label="Models",
    with_state: bool = True,
    with_categories: bool = True,
    with_description: bool = True,
    with_sizes: bool = True,
) -> list[str]:
    if items is None and models is not None:
        items = models2tree(
            models=models,
            expanded=expanded,
            with_state=with_state,
            with_categories=with_categories,
            with_description=with_description,
            with_sizes=with_sizes,
        )

    if items is None:
        items = []

    selected_items = sac.tree(
        items,
        label=label,
        index=0,
        align="center",
        size="md",
        icon="table",
        open_all=expanded,
        checkbox=True,
    )

    selected_items = [
        item for item in selected_items if isinstance(item, str) and ":" in item
    ]
    return selected_items


def _pull_single_model(name: str, progress_bar: DeltaGenerator | None):
    """
    Worker function pulling a single model and updating its progress bar.

    Expects helper.models.pull(name, stream=True) to yield dict-like chunks with
    optional 'completed' and 'total' keys (Ollama-style JSON stream).
    """
    completed = 0
    total = None

    if progress_bar is None:
        debug(f"Missing progress bar for {name}; skipping initialization")
        return

    try:
        progress_bar.progress(0.0, text=f"Pulling {name} …")
    except Exception as exc:
        debug(f"Error initializing progress bar for model {name}: {exc}")

    try:
        for chunk in helper.models.pull(name, stream=True):
            # be defensive about chunk structure
            if not isinstance(chunk, dict):
                continue

            completed = chunk.get("completed", completed)
            total = chunk.get("total", total)

            # if we have size information, show real percentage
            if total and total > 0:
                frac = completed / total
                progress_bar.progress(
                    min(max(frac, 0.0), 1.0),
                    text=f"{name}: {completed / 1_048_576:.1f} MB / {total / 1_048_576:.1f} MB",
                )
            else:
                # no size info – just keep the bar in "indeterminate-ish" state
                progress_bar.progress(0.5, text=f"Pulling {name} …")

        # finished
        progress_bar.progress(1.0, text=f"{name}: done")

    except Exception as exc:
        progress_bar.progress(0.0, text=f"{name}: error")
        st.error(f"Error pulling model '{name}': {exc}")


def pull_models_with_progress(model_names: list[str], max_workers: int | None = None):
    """
    Pulls all given Ollama models in parallel and shows a progress bar per model.
    """
    if not model_names:
        st.info("No models to pull.")
        return

    st.subheader("Pulling Ollama models")

    # create one progress bar per model
    bars: dict[str, DeltaGenerator] = {
        name: st.progress(0.0, text=f"{name}: waiting") for name in model_names
    }

    if max_workers is None:
        max_workers = min(4, len(model_names))  # simple default

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_pull_single_model, name, bars[name]): name
            for name in model_names
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as exc:
                # safety net; _pull_single_model already shows error
                st.error(f"Unexpected error pulling '{name}': {exc}")
