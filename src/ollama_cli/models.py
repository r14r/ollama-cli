#!/usr/bin/env python3
from . import compose


# ============================================================
#  Model management operations
# ============================================================
def ensure_model_exists(model: str) -> bool:
    """Check if a model is installed."""
    compose.ensure_service_running()
    result = compose.compose_exec(["ollama", "list"], check=True, capture_output=True)
    for i, line in enumerate(result.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        if i == 0 and line.startswith("NAME"):
            continue
        parts = line.split()
        if parts and parts[0] == model:
            return True
    return False


def ensure_model_pulled(model: str) -> None:
    """Ensure a model is pulled, pull if necessary."""
    if ensure_model_exists(model):
        return
    print(f"Model '{model}' is not available locally. Pulling it now...")
    compose.compose_exec(["ollama", "pull", model], check=True)


def get_default_models() -> list[str]:
    """Get the list of default models to install."""
    import os
    import shlex

    env_models = os.environ.get("OLLAMA_DEFAULT_MODELS", "").strip()
    if env_models:
        return shlex.split(env_models)
    return [
        "llama3.2:1b",
        "gemma4:latest",
        "gemma4:e2b",
        "gemma3:1b",
        "gemma3:4b",
        "phi4-mini",
        "phi4-reasoning",
        "phi4-mini-reasoning",
        "phi3-mini",
        "deepseek-r1",
        "qwen3.6:latest",
        "mistral:latest",
        "mistral-nemo:latest",
        "nomic-embed-text-v2-moe",
    ]


def get_list_of_installed_models() -> list[str]:
    """Get list of all installed models."""
    compose.ensure_service_running()
    response = compose.compose_exec(["ollama", "list"], check=True, capture_output=True)
    model_names: list[str] = []
    for i, line in enumerate(response.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        if i == 0 and line.startswith("NAME"):
            continue
        parts = line.split()
        if parts:
            model_names.append(parts[0])
    return model_names
