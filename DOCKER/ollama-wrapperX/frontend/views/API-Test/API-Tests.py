import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.helper_ollama import helper
from lib.helper_streamlit import (
    models_view_table,
    pull_models_with_progress
)




def render() -> None:
    st.header("Model management")

    tab_list, tab_show, tab_pull, tab_delete = st.tabs(
        ["List", "Show", "Pull", "Delete"]
    )

    # ------------------------------------------------------------------
    # LIST TAB
    # ------------------------------------------------------------------
    with tab_list:
        st.subheader("List Models")

        if st.button("Refresh"):
            helper.refresh()

        installed_models_with_details = helper.get_installed_models_with_details()
        models_view_table(installed_models_with_details)

    # ------------------------------------------------------------------
    # SHOW TAB
    # ------------------------------------------------------------------
    with tab_show:
        st.subheader("Show Model")

        installed_names = helper.get_installed_models_names()
        installed_models = helper.get_installed_models_with_details()
        if installed_names:
            model_name = st.selectbox("Select a model", installed_names)
            model_obj = installed_models.initial_models.get(model_name)
            description = model_obj.__dict__ if model_obj else {}

            st.json(description)
        else:
            st.info("No installed models available.")

    # ------------------------------------------------------------------
    # PULL TAB
    # ------------------------------------------------------------------
    with tab_pull:
        st.subheader("Pull Models")

        # --- session state for "latest this session" tracking (base names) ---
        if "pulled_models" not in st.session_state:
            st.session_state["pulled_models"] = set()
        pulled_set: set[str] = st.session_state["pulled_models"]

        # --- get installed models and normalize to base names (before ':') ---
        installed_base_names: set[str] = set()
        for entry in helper.get_installed_models_with_details():
            name = entry.name

            if not name:
                continue
            base = name.split(":", 1)[0]
            installed_base_names.add(base)

        # --- get available models from web (scraped library) ---
        force_reload = st.button("Force Reload")
        if force_reload:
            helper.refresh()

        available_models = [
            model.to_dict() for model in helper.get_available_models_with_details()
        ]

        df = pd.DataFrame(available_models)

        # --- collect categories for filter (from string column) ---
        categories = set()
        for model in available_models:
            for category in model.get("categories", ""):
                c = category.strip()
                if c:
                    categories.add(c)

        available_categories = sorted(categories)

        # --- filter by category (single selection) ---
        selected_category = st.segmented_control(
            "Filter by Category",
            available_categories,
            selection_mode="single",
        )

        if selected_category:
            mask = df["categories"].fillna("").apply(
                lambda cats: selected_category in [
                    c.strip() for c in cats
                ]
            )
            df_filtered = df.loc[mask].copy()
        else:
            df_filtered = df.copy()

        # --- sanity: we need 'name' from web list as base name ---
        if "name" not in df_filtered.columns:
            st.error("No 'name' column present in model data.")
            st.stop()

        # --- convert categories to tag-like lists with emojis for display ---
        CATEGORY_ICONS = {
            "tools": "🧰",
            "vision": "👁️",
            "embedding": "🧩",
            "cloud": "☁️",
            "thinking": "🧠",
        }

        def to_category_list(value: str) -> list[str]:
            items: list[str] = []
            for raw in str(value):
                raw = raw.strip()
                if not raw:
                    continue

                icon = CATEGORY_ICONS.get(raw.lower(), "🏷️")
                items.append(f"{icon} {raw}")
            return items

        df_filtered["categories"] = df_filtered["categories"].fillna("").apply(
            to_category_list
        )

        # --- status column: based on base name + "pulled this session" ---
        def compute_status(base_name: str) -> str:
            if base_name not in installed_base_names:
                return "❌ not installed"
            if base_name in pulled_set:
                return "✅ installed (latest)"
            return "🟢 installed"

        df_filtered["status"] = df_filtered["name"].apply(compute_status)

        # --- checkbox column for selecting rows to pull (must be first) ---
        df_filtered.insert(0, "pull", False)

        # --- column config ---
        column_config = {
            "pull": st.column_config.CheckboxColumn(
                "Select",
                help="Select this model to pull",
            ),
            "status": st.column_config.TextColumn(
                "Status",
                help="Installed / latest state "
                     "(latest means pulled in this session)",
                width="medium",
            ),
            "name": st.column_config.TextColumn("Model Name"),
            "categories": st.column_config.ListColumn(
                "Categories",
                help="Model categories",
                width="large",
            ),
            "description": st.column_config.TextColumn("Description"),
            "sizes": st.column_config.TextColumn("Sizes"),
            "downloads": st.column_config.TextColumn("Downloads"),
            "updated": st.column_config.TextColumn("Updated"),
        }

        st.markdown("#### Available models")

        try:
            edited_df = st.data_editor(
            data=df_filtered,
            width='stretch',
            hide_index=True,
            column_config=column_config,
            key="models_editor",
        )
        except Exception as e:
            st.markdown(f"**could no tsetup table**: {e}")

        # ------------------------------------------------------------------
        # Pull selected model(s)
        # ------------------------------------------------------------------
        st.markdown("#### Pull selected model(s)")

        if st.button("Pull selected model(s)"):
            selected_rows = edited_df.index[edited_df["pull"]].tolist()

            if not selected_rows:
                st.warning("Please select at least one model.")
            else:
                selected_models = [edited_df.loc[idx, "name"] for idx in selected_rows]

                # Single selection → detailed streaming progress
                if len(selected_models) == 1:
                    model_name = selected_models[0]  # base name from web
                    st.info(f"Pulling model: {model_name}")
                    pull_models_with_progress(model_name=model_name)
                    base = model_name.split(":", 1)[0]
                    st.session_state["pulled_models"].add(base)
                    st.rerun()

                # Multiple selections → parallel pulls with overall progress
                else:
                    st.info(f"Pulling {len(selected_models)} models…")

                    progress = st.progress(0, text="Starting pulls…")
                    status_placeholder = st.empty()

                    total = len(selected_models)
                    completed = 0
                    max_workers = min(4, total)

                def pull_simple(name: str):
                    # name is base (e.g. "llama3.1")
                    return helper.models.pull(name, stream=False)

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {
                            executor.submit(pull_simple, name): name
                            for name in selected_models
                        }

                        for future in as_completed(futures):
                            name = futures[future]
                            try:
                                future.result()
                                completed += 1
                                base = name.split(":", 1)[0]
                                st.session_state["pulled_models"].add(base)
                                percent = int(completed / total * 100)
                                progress.progress(
                                    percent,
                                    text=f"Pulled {completed}/{total} models "
                                         f"(last: {name})",
                                )
                                status_placeholder.success(
                                    f"Model `{name}` pulled successfully."
                                )
                            except Exception as e:
                                completed += 1
                                percent = int(completed / total * 100)
                                progress.progress(
                                    percent,
                                    text=f"Error pulling {name} "
                                         f"({completed}/{total})",
                                )
                                status_placeholder.error(
                                    f"Error pulling `{name}`: {e}"
                                )

                    progress.progress(100, text="All pull tasks finished.")
                    st.rerun()

    # ------------------------------------------------------------------
    # DELETE TAB (placeholder)
    # ------------------------------------------------------------------
    with tab_delete:
        st.subheader("Delete Models")
        st.info("Not implemented yet.")


if __name__ == "__main__":
    render()
