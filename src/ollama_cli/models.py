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
    import sys
    import configparser
    from pathlib import Path

    env_models = os.environ.get("OLLAMA_DEFAULT_MODELS", "").strip()
    if env_models:
        return shlex.split(env_models)

    config_file = Path.home() / ".ollama-cli" / "setup.yml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                ollama_cfg = data.get("ollama")
                if isinstance(ollama_cfg, dict):
                    models_val = ollama_cfg.get("default_models")
                    if isinstance(models_val, list):
                        return [str(m).strip() for m in models_val if str(m).strip()]
                    elif isinstance(models_val, str):
                        if "," in models_val:
                            return [m.strip() for m in models_val.split(",") if m.strip()]
                        else:
                            return [m.strip() for m in models_val.split() if m.strip()]
        except Exception as e:
            print(f"Warning: Failed to parse setup.yml: {e}", file=sys.stderr)

    return [
        "llama3.2:1b",
        "gemma4:latest",
        "gemma4:e2b",
        "gemma3:1b",
        "gemma3:4b",
        "phi4-mini",
        "phi4-reasoning",
        "phi4-mini-reasoning",
        "phi3:mini",
        "deepseek-r1",
        "qwen3.6:latest",
        "mistral:latest",
        "mistral-nemo:latest",
        "nomic-embed-text-v2-moe",
    ]


def get_group_models(group: str) -> list[str]:
    """Get the list of models for a specific group from setup.yml."""
    import sys
    import yaml
    from pathlib import Path

    config_file = Path.home() / ".ollama-cli" / "setup.yml"
    if not config_file.exists():
        print(f"Error: Setup file does not exist at {config_file}. Run 'setup' command first.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        models_val = None
        group_key = f"{group}_models"
        
        if data and isinstance(data, dict):
            ollama_cfg = data.get("ollama")
            if isinstance(ollama_cfg, dict):
                models_val = ollama_cfg.get(group_key)
            
            if models_val is None:
                models_val = data.get(group_key)

        if models_val is None:
            print(f"Error: Group '{group_key}' not found in setup.yml", file=sys.stderr)
            sys.exit(1)

        if isinstance(models_val, list):
            return [str(m).strip() for m in models_val if str(m).strip()]
        elif isinstance(models_val, str):
            if "," in models_val:
                return [m.strip() for m in models_val.split(",") if m.strip()]
            else:
                return [m.strip() for m in models_val.split() if m.strip()]
        else:
            print(f"Error: Group '{group_key}' must be a list of models or a string", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: Failed to parse setup.yml: {e}", file=sys.stderr)
        sys.exit(1)


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
