#!/usr/bin/env python3
"""
CLI for the Ollama wrapper – mirrors all functions of the Streamlit app.

Usage (run from the frontend/ directory):
  python cli.py models list
  python cli.py models list --local
  python cli.py models list --remote
  python cli.py models list --category tools
  python cli.py models show llama3
  python cli.py models pull llama3
  python cli.py models delete llama3
  python cli.py chat llama3 "Why is the sky blue?"
  python cli.py generate llama3 "Write a haiku about Python."
  python cli.py status
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Bootstrap: ensure the frontend/ directory is on sys.path so that `lib`
# imports work regardless of where the script is invoked from.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_json(data: object) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def _format_size(size_obj) -> str:
    """Return a human-readable string from a ModuleSize or plain string."""
    if hasattr(size_obj, "size"):
        installed = " ✓" if getattr(size_obj, "installed", False) else ""
        return f"{size_obj.size}{installed}"
    return str(size_obj)


def _print_model_table(models) -> None:
    """Pretty-print a Models collection as a compact table."""
    rows = []
    for model in models:
        state = "✓" if model.installed else " "
        cats = ", ".join(model.categories) if model.categories else "-"
        sizes = "  ".join(_format_size(s) for s in (model.sizes or []))
        src = getattr(model, "source", "-")
        rows.append((state, model.name, src, cats, sizes))

    if not rows:
        click.echo("No models found.")
        return

    w_name = max(len(r[1]) for r in rows)
    w_src  = max(len(r[2]) for r in rows)
    w_cats = max(len(r[3]) for r in rows)
    header = f"  {'Name':<{w_name}}  {'Source':<{w_src}}  {'Categories':<{w_cats}}  Sizes"
    click.echo(header)
    click.echo("-" * len(header))
    for state, name, src, cats, sizes in rows:
        mark = "✓" if state == "✓" else " "
        click.echo(f"{mark} {name:<{w_name}}  {src:<{w_src}}  {cats:<{w_cats}}  {sizes}")


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(prog_name="ollama-cli")
def cli() -> None:
    """Ollama wrapper CLI – manage models, chat, generate, and check status."""


# ---------------------------------------------------------------------------
# models sub-group
# ---------------------------------------------------------------------------

@cli.group()
def models() -> None:
    """Model management commands."""


@models.command("list")
@click.option("--local", "source", flag_value="local", help="Show only installed (local) models.")
@click.option("--remote", "source", flag_value="remote", help="Show only remote (library) models.")
@click.option("--all", "source", flag_value="all", default=True, help="Show all models (default).")
@click.option("--category", "-c", multiple=True, help="Filter by category (can be repeated).")
@click.option("--sort-by", "-s",
    type=click.Choice(["name", "category", "order", "size"], case_sensitive=False),
    default="name",
    show_default=True,
    help="Sort models by field."
)
@click.option("--sort-order", "-o",
    type=click.Choice(["asc", "desc"], case_sensitive=False),
    default="asc",
    show_default=True,
    help="Sort order."
)
@click.option(
    "--filter", "-f", "name_filter",
    default="",
    help="Filter models by name substring."
)
@click.option("--format", "fmt",
    type=click.Choice(["table", "json", "names"]),
    default="table",
    show_default=True,
    help="Output format.",
)
def models_list(source: str, category: tuple, fmt: str, sort_by: str, sort_order: str, name_filter: str) -> None:
    """List models – all, local, or remote."""
    from lib.helper_ollama import helper, Models
    from lib.helper_ollama.models import MODELS_SOURCE

    click.echo(f"Fetching models (source={source}) …", err=True)

    if source == "local":
        all_models = helper.get_installed_models_with_details()
    elif source == "remote":
        src = MODELS_SOURCE.web
        all_models = Models.from_source(source=src)
    else:
        all_models = helper.get_available_models_with_details()

    # Apply category filter
    if category:
        all_models = all_models.get_by_categories(list(category))


    # Apply name filter
    if name_filter:
        needle = name_filter.casefold()

        filtered_items = [
            model
            for model in all_models
            if needle in str(getattr(model, "name", "")).casefold()
        ]
        all_models = Models(filtered_items)
    # Apply sorting
    if sort_by:
        reverse = sort_order.lower() == "desc"

        def _get_attr(model, key):
            # defensive access (works for objects or dict-like)
            if hasattr(model, key):
                return getattr(model, key)
            if isinstance(model, dict):
                return model.get(key)
            return None

        all_models = sorted(
            all_models,
            key=lambda m: (_get_attr(m, sort_by) is None, _get_attr(m, sort_by)),
            reverse=reverse,
        )

    if fmt == "names":
        for name in all_models.get_names():
            click.echo(name)
    elif fmt == "json":
        _print_json(all_models.to_dict())
    else:
        _print_model_table(all_models)

    click.echo(f"\nTotal: {len(all_models)}", err=True)


@models.command("show")
@click.argument("name")
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["json", "text"]),
    default="json",
    show_default=True,
)
def models_show(name: str, fmt: str) -> None:
    """Show details of an installed model."""
    from lib.helper_ollama.model import Model
    from lib.helper_ollama.types import RESPONSESTATES

    click.echo(f"Fetching details for '{name}' …", err=True)
    model = Model(name=name)
    state = model.show()

    if state.state == RESPONSESTATES.OK:
        details = dict(state.response) if hasattr(state.response, "__iter__") else vars(state.response)
        if fmt == "json":
            _print_json(details)
        else:
            for key, value in details.items():
                click.echo(f"{key}: {value}")
    else:
        click.echo(f"Error: {state.message}", err=True)
        sys.exit(1)


@models.command("pull")
@click.argument("name")
@click.option("--stream/--no-stream", default=False, show_default=True, help="Stream pull progress.")
def models_pull(name: str, stream: bool) -> None:
    """Pull (download/install) a model from the Ollama library."""
    from lib.helper_ollama.model import Model
    from lib.helper_ollama.types import RESPONSESTATES

    click.echo(f"Pulling model '{name}' (stream={stream}) …")
    model = Model(name=name)
    state = model.pull(stream=stream)

    if state.state == RESPONSESTATES.OK:
        click.echo(f"✓ Successfully pulled '{name}': {state.message}")
    else:
        click.echo(f"✗ Failed to pull '{name}': {state.message}", err=True)
        sys.exit(1)


@models.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def models_delete(name: str, yes: bool) -> None:
    """Delete a locally installed model."""
    from lib.helper_ollama.model import Model
    from lib.helper_ollama.types import RESPONSESTATES

    if not yes:
        click.confirm(f"Delete model '{name}'?", abort=True)

    model = Model(name=name)
    state = model.delete()

    if state.state == RESPONSESTATES.OK:
        click.echo(f"✓ Deleted '{name}'.")
    else:
        click.echo(f"✗ Failed to delete '{name}': {state.message}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# chat command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("model_name")
@click.argument("message")
@click.option("--system", "-s", default=None, help="Optional system prompt.")
@click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
@click.option("--format", "-f", "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def chat(model_name: str, message: str, system: Optional[str], temperature: Optional[float], fmt: str) -> None:
    """Send a chat message to a model and print the reply."""
    from lib.helper_ollama.model import Model
    from lib.helper_ollama.types import RESPONSESTATES

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    model = Model(name=model_name)
    state = model.chat(messages=messages, temperature=temperature)

    if state.state == RESPONSESTATES.OK:
        response = state.response
        if fmt == "json":
            _print_json(dict(response) if hasattr(response, "__iter__") else vars(response))
        else:
            # Extract assistant content from ChatResponse
            try:
                content = response.message.content
            except AttributeError:
                try:
                    content = response["message"]["content"]
                except (KeyError, TypeError):
                    content = str(response)
            click.echo(content)
    else:
        click.echo(f"Error: {state.message}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("model_name")
@click.argument("prompt")
@click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
@click.option("--format", "-f", "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def generate(model_name: str, prompt: str, temperature: Optional[float], fmt: str) -> None:
    """Generate a completion from a model."""
    from lib.helper_ollama.model import Model
    from lib.helper_ollama.types import RESPONSESTATES

    model = Model(name=model_name)
    state = model.generate(prompt=prompt, temperature=temperature)

    if state.state == RESPONSESTATES.OK:
        response = state.response
        if fmt == "json":
            _print_json(dict(response) if hasattr(response, "__iter__") else vars(response))
        else:
            try:
                content = response.response
            except AttributeError:
                try:
                    content = response["response"]
                except (KeyError, TypeError):
                    content = str(response)
            click.echo(content)
    else:
        click.echo(f"Error: {state.message}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def status(fmt: str) -> None:
    """Show Ollama and gateway status."""
    import requests as _requests
    from lib.openapi import OLLAMA_OPENAPI_URL, GATEWAY_OPENAPI_URL

    result: dict = {
        "ollama_url": OLLAMA_OPENAPI_URL,
        "gateway_url": GATEWAY_OPENAPI_URL,
        "ollama": {},
        "gateway": {},
    }

    # Ollama version
    try:
        r = _requests.get(f"{OLLAMA_OPENAPI_URL}/api/version", timeout=5)
        r.raise_for_status()
        result["ollama"] = r.json()
    except Exception as exc:
        result["ollama"] = {"error": str(exc)}

    # Gateway health
    try:
        r = _requests.get(f"{GATEWAY_OPENAPI_URL}/extended/monitoring/health", timeout=5)
        r.raise_for_status()
        result["gateway"] = r.json()
    except Exception as exc:
        result["gateway"] = {"error": str(exc)}

    if fmt == "json":
        _print_json(result)
    else:
        click.echo(f"Ollama  : {result['ollama_url']}")
        click.echo(f"         {result['ollama']}")
        click.echo(f"Gateway : {result['gateway_url']}")
        click.echo(f"         {result['gateway']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
