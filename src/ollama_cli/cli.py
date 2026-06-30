#!/usr/bin/env python3
import sys
import os

if "--debug" in sys.argv:
    os.environ["OLLAMA_DEBUG"] = "1"

import argparse
import contextlib
import re
import subprocess
from pathlib import Path
from typing import Any

from . import blobs, compose, models, remote, utils

# ============================================================
#  Global configurations
# ============================================================
LAUNCH_MODELS = {
    "claude": os.environ.get("OLLAMA_LAUNCH_CLAUDE_MODEL", "qwen2.5:7b-instruct"),
    "opencode": os.environ.get("OLLAMA_LAUNCH_OPENCODE_MODEL", "qwen2.5:7b-instruct"),
    "chat": os.environ.get("OLLAMA_LAUNCH_CHAT_MODEL", "mistral:7b-instruct"),
    "fast": os.environ.get("OLLAMA_LAUNCH_FAST_MODEL", "llama3.2:1b"),
    "reason": os.environ.get("OLLAMA_LAUNCH_REASON_MODEL", "deepseek-r1"),
    "embed": os.environ.get("OLLAMA_LAUNCH_EMBED_MODEL", "nomic-embed-text"),
    "hermes": os.environ.get("OLLAMA_LAUNCH_HERMES_MODEL", "phi4-mini"),
}

WRAPPER_COMMANDS = {
    "-h",
    "--help",
    "help",
    "up",
    "down",
    "build",
    "status",
    "version",
    "--version",
    "profiles",
    "install-defaults",
    "launch",
    "list-remote",
    "shell",
    "update-models",
    "blobs",
    "models",
    "list",
    "ls",
    "setup",
    "install-models",
}

DEBUG_ENABLED = os.environ.get("OLLAMA_DEBUG", "").lower() in {"1", "true", "yes", "on"}


# ============================================================
#  Subcommands handlers
# ============================================================
def cmd_up(args: argparse.Namespace) -> None:
    """Start the Ollama service stack."""
    compose.run_cmd(compose.compose_build_cmd("up", "-d"), check=True)


def cmd_down(args: argparse.Namespace) -> None:
    """Stop the Ollama service stack."""
    compose.run_cmd(compose.compose_build_cmd("down"), check=True)


def cmd_build_service(args: argparse.Namespace) -> None:
    """Pull base image and rebuild the Ollama service."""
    compose.run_cmd(["docker", "pull", "ollama/ollama:latest"], check=True)
    compose.run_cmd(compose.compose_build_cmd("build"), check=True)


def cmd_status(args: argparse.Namespace) -> None:
    """Show container and model status."""
    compose.ensure_compose_file()
    print(f"Compose file : {compose.COMPOSE_FILE}")
    print(f"Project name : {compose.PROJECT_NAME}")
    print(f"Service      : {compose.SERVICE}")
    print()

    print("Container status:")
    with contextlib.suppress(subprocess.CalledProcessError):
        compose.run_cmd(compose.compose_build_cmd("ps", compose.SERVICE), check=True)
    print()

    if compose.is_service_running():
        print("Ollama models:")
        with contextlib.suppress(subprocess.CalledProcessError):
            compose.compose_exec(["ollama", "list"], check=True)
        print()
        print("Running models:")
        with contextlib.suppress(subprocess.CalledProcessError):
            compose.compose_exec(["ollama", "ps"], check=True)
    else:
        print(f"Service '{compose.SERVICE}' is not running.")


def cmd_profiles(args: argparse.Namespace) -> None:
    """List launch profiles."""
    print("Available launch profiles:")
    for name, model in LAUNCH_MODELS.items():
        print(f"  {name:<10} -> {model}")


def cmd_install_defaults(args: argparse.Namespace) -> None:
    """Pull default model set into the Ollama volume."""
    compose.ensure_service_running()
    defaults = models.get_default_models()
    print(f"Pulling default models into Ollama volume for service '{compose.SERVICE}'...")
    print("Models:")
    for model in defaults:
        print(f"  {model}")
    print()

    for model in defaults:
        print(f"==> ollama pull {model}")
        compose.compose_exec(["ollama", "pull", model], check=True)
        print()

    print("Done. Current tags:")
    with contextlib.suppress(subprocess.CalledProcessError):
        compose.compose_exec(["ollama", "list"], check=True)


def cmd_install_models(args: argparse.Namespace) -> None:
    """Pull model set of a specific group into the Ollama volume."""
    compose.ensure_service_running()
    group_models = models.get_group_models(args.group)
    print(f"Pulling group '{args.group}' models into Ollama volume for service '{compose.SERVICE}'...")
    print("Models:")
    for model in group_models:
        print(f"  {model}")
    print()

    for model in group_models:
        print(f"==> ollama pull {model}")
        compose.compose_exec(["ollama", "pull", model], check=True)
        print()

    print("Done. Current tags:")
    with contextlib.suppress(subprocess.CalledProcessError):
        compose.compose_exec(["ollama", "list"], check=True)


def cmd_launch_model(args: argparse.Namespace) -> None:
    """Launch a predefined profile."""
    profile = args.profile
    prompt_parts = args.prompt
    model = LAUNCH_MODELS.get(profile)
    if not model:
        print(f"ERROR: unknown launch profile '{profile}", file=sys.stderr)
        print("Run 'profiles' to see available profiles.", file=sys.stderr)
        sys.exit(2)

    compose.ensure_service_running()
    models.ensure_model_pulled(model)

    print(f"Launching profile '{profile}' with model '{model}'...")

    cmd = ["ollama", "run", model]
    if prompt_parts:
        cmd.append(" ".join(prompt_parts))
    compose.compose_exec_or_exec(cmd)


def cmd_shell(args: argparse.Namespace) -> None:
    """Open a shell inside the Ollama container."""
    compose.ensure_service_running()
    compose.compose_exec_or_exec(["bash"])


def cmd_update_models(args: argparse.Namespace) -> None:
    """Pull the latest version for all installed models."""
    installed = models.get_list_of_installed_models()
    for model in installed:
        print(f"Update '{model}'")
        compose.compose_exec(["ollama", "pull", model], check=True)


def cmd_setup(args: argparse.Namespace) -> None:
    """Setup the environment and edit the configuration file."""
    config_dir = Path.home() / ".ollama-cli"
    config_file = config_dir / "setup.yml"

    config_dir.mkdir(parents=True, exist_ok=True)

    if not config_file.exists():
        models_list = "\n".join(f"    - {m}" for m in models.get_default_models())
        default_content = f"""ollama:
  # List of default models to pull when running 'install-defaults'
  default_models:
{models_list}
"""
        config_file.write_text(default_content, encoding="utf-8")
        print(f"Created setup file: {config_file}")
    else:
        print(f"Setup file already exists: {config_file}")

    if args.edit:
        editor = os.environ.get("EDITOR")
        if editor:
            subprocess.run([editor, str(config_file)])
        else:
            if sys.platform == "darwin":
                subprocess.run(["open", "-e", str(config_file)])
            else:
                subprocess.run(["nano", str(config_file)])


def cmd_list(args: argparse.Namespace) -> None:
    """List local models in docker container."""
    compose.ensure_service_running()
    result = compose.compose_exec(["ollama", "list"], check=True, capture_output=True)

    lines = result.stdout.splitlines()
    if not lines:
        print("No models found.")
        return

    header = lines[0].strip()
    if not header.startswith("NAME"):
        print(result.stdout)
        return

    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
        if len(parts) >= 4:
            rows.append(
                {
                    "name": parts[0],
                    "id": parts[1],
                    "size": parts[2],
                    "modified": parts[3],
                    "size_bytes": utils.parse_size_to_bytes(parts[2]),
                    "modified_seconds": utils.parse_relative_time_to_seconds(parts[3]),
                }
            )
        elif len(parts) == 3:
            rows.append(
                {
                    "name": parts[0],
                    "id": parts[1],
                    "size": parts[2],
                    "modified": "unknown",
                    "size_bytes": utils.parse_size_to_bytes(parts[2]),
                    "modified_seconds": 9999999999,
                }
            )

    # Sort choice
    sort_by = args.sort_by or "name"
    reverse = args.sort_desc if hasattr(args, "sort_desc") else False
    if hasattr(args, "sort_asc") and args.sort_asc:
        reverse = False

    if sort_by == "size":
        rows.sort(key=lambda r: r["size_bytes"], reverse=reverse)
    elif sort_by in ("modified", "date"):
        rows.sort(key=lambda r: r["modified_seconds"], reverse=reverse)
    elif sort_by == "id":
        rows.sort(key=lambda r: r["id"].lower(), reverse=reverse)
    else:  # name
        rows.sort(key=lambda r: r["name"].lower(), reverse=reverse)

    if not rows:
        print("No models found.")
        return

    widths = {
        "NAME": max(len("NAME"), *(len(r["name"]) for r in rows)),
        "ID": max(len("ID"), *(len(r["id"]) for r in rows)),
        "SIZE": max(len("SIZE"), *(len(r["size"]) for r in rows)),
        "MODIFIED": max(len("MODIFIED"), *(len(r["modified"]) for r in rows)),
    }

    header_str = (
        f"{"NAME".ljust(widths["NAME"])}  "
        f"{"ID".ljust(widths["ID"])}  "
        f"{"SIZE".ljust(widths["SIZE"])}  "
        f"{"MODIFIED".ljust(widths["MODIFIED"])}"
    )
    print(header_str)
    for r in rows:
        row_str = (
            f"{r['name'].ljust(widths['NAME'])}  "
            f"{r['id'].ljust(widths['ID'])}  "
            f"{r['size'].ljust(widths['SIZE'])}  "
            f"{r['modified'].ljust(widths['MODIFIED'])}"
        )
        print(row_str)


def cmd_help(args: argparse.Namespace) -> None:
    """Show help message."""
    parser = build_parser()
    parser.print_help()
    sys.exit(0)


# ============================================================
#  Argument parsing
# ============================================================
def get_install_source() -> str:
    """Determine how the package was installed."""
    if hasattr(sys, "oxidized"):
        return "pyoxidizer"
    elif getattr(sys, "frozen", False):
        return "pyinstaller"

    argv0 = sys.argv[0] if (sys.argv and sys.argv[0] is not None) else ""
    if "SHIV_ENTRY_POINT" in os.environ or ".pyz" in argv0:
        return "shiv"
    else:
        return "source"


class CustomArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        help_text = super().format_help()
        cmds = [
            "up", "down", "build", "status", "version", "profiles",
            "install-defaults", "launch", "list-remote", "shell",
            "update-models", "blobs", "models", "setup", "install-models"
        ]
        
        # Replace subcommands inside choices list (e.g. {up,down,...})
        def replace_choices(match):
            text = match.group(0)
            for cmd in cmds:
                text = re.sub(fr"(?<=[{{,]){cmd}(?=[}},])", f"--{cmd}", text)
            return text

        help_text = re.sub(r"\{[a-zA-Z0-9_,-]+\}", replace_choices, help_text)

        # Replace subcommands definition lines in positional arguments
        for cmd in cmds:
            help_text = re.sub(fr"^    {cmd}(?=\s)", f"    --{cmd}", help_text, flags=re.MULTILINE)
        return help_text

    def format_usage(self) -> str:
        usage = super().format_usage()
        cmds = [
            "up", "down", "build", "status", "version", "profiles",
            "install-defaults", "launch", "list-remote", "shell",
            "update-models", "blobs", "models", "setup", "install-models"
        ]
        def replace_choices(match):
            text = match.group(0)
            for cmd in cmds:
                text = re.sub(fr"(?<=[{{,]){cmd}(?=[}},])", f"--{cmd}", text)
            return text

        usage = re.sub(r"\{[a-zA-Z0-9_,-]+\}", replace_choices, usage)
        return usage


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = CustomArgumentParser(
        prog="ollama-cli",
        description=(
            "Extended Ollama CLI helper and Docker Compose wrapper.\n\n"
            "Wrapper commands:\n"
            "  --up               : Start the Ollama service stack\n"
            "  --down             : Stop the Ollama service stack\n"
            "  --build            : Pull base image and rebuild the Ollama service\n"
            "  --status           : Show container and model status\n"
            "  --profiles         : List launch profiles\n"
            "  --install-defaults : Pull default model set into the Ollama volume\n"
            "  --launch           : Launch a predefined profile\n"
            "  --list-remote      : List models from the Ollama library website\n"
            "  --shell            : Open a shell inside the Ollama container\n"
            "  --update-models    : Pull the latest version for all installed models\n"
            "  --setup            : Set up environment and default models\n"
            "  --install-models   : Pull a specific group of models from setup.yml\n"
            "  --blobs            : Inspect blobs / manifests / orphans\n"
            "  --models           : List models with blob counts and total sizes\n"
            "  list / ls          : List local models with sort options\n\n"
            "Other commands are proxied directly to 'ollama' in the container."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"ollama-cli version 1.1.1",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug log output",
    )

    subparsers = parser.add_subparsers(dest="command")

    # ---------------- up ----------------
    subparsers.add_parser("up", help="Start the Ollama service stack")

    # ---------------- down ----------------
    subparsers.add_parser("down", help="Stop the Ollama service stack")

    # ---------------- build ----------------
    subparsers.add_parser(
        "build", help="Pull latest base image and rebuild the Ollama service"
    )

    # ---------------- status ----------------
    subparsers.add_parser("status", help="Show container and model status")

    # ---------------- version ----------------
    subparsers.add_parser("version", help="Show Ollama version inside the container")

    # ---------------- shell ----------------
    subparsers.add_parser("shell", help="Open a shell inside the Ollama container")

    # ---------------- profiles ----------------
    subparsers.add_parser("profiles", help="List launch profiles")

    # ---------------- install-defaults ----------------
    subparsers.add_parser(
        "install-defaults", help="Pull the default model set into the Ollama volume"
    )

    # ---------------- install-models ----------------
    p_install_models = subparsers.add_parser(
        "install-models", help="Pull a specific group of models from setup.yml"
    )
    p_install_models.add_argument(
        "--group", required=True, help="Model group name (e.g. reasoning, fast)"
    )

    # ---------------- setup ----------------
    p_setup = subparsers.add_parser(
        "setup", help="Set up environment and default models"
    )
    p_setup.add_argument(
        "--edit", action="store_true", help="Edit the setup.yml file using your default editor"
    )

    # ---------------- update-models ----------------
    subparsers.add_parser(
        "update-models", help="Pull the latest version for all installed models"
    )

    # ---------------- launch ----------------
    p_launch = subparsers.add_parser("launch", help="Launch a predefined profile")
    p_launch.add_argument(
        "profile", choices=sorted(LAUNCH_MODELS.keys()), help="Launch profile name"
    )
    p_launch.add_argument("prompt", nargs="*", help="Optional prompt text")

    # ---------------- list-remote ----------------
    p_remote = subparsers.add_parser(
        "list-remote", help="List models from the Ollama library website"
    )
    p_remote.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of rows to show; use 0 for all",
    )
    p_remote.add_argument(
        "--with-description",
        action="store_true",
        help="Print the description below each row",
    )
    p_remote.add_argument(
        "--filter",
        dest="filter_capabilities",
        action="append",
        default=[],
        help="Filter by capability; may be specified multiple times",
    )
    p_remote.add_argument(
        "--sort-by",
        choices=["order", "capability", "size", "date", "name"],
        default="name",
        help="Sort output by capability, size, date, name, or keep original order",
    )
    p_remote.add_argument(
        "--force",
        action="store_true",
        help="Bypass/refresh the cache of remote models metadata",
    )
    p_remote.add_argument(
        "--show-cache",
        action="store_true",
        help="Show the cache folder and list cached files",
    )
    p_remote.add_argument(
        "--model",
        default=None,
        help="Specify model name to show cached JSON content (used with --show-cache)",
    )

    # ---------------- list ----------------
    p_list = subparsers.add_parser("list", help="List local models in docker container")
    p_list.add_argument(
        "--sort-by",
        choices=["name", "size", "modified", "id"],
        default="name",
        help="Sort models by column",
    )
    p_list.add_argument(
        "--sort-asc", action="store_true", help="Sort ascending (default)"
    )
    p_list.add_argument("--sort-desc", action="store_true", help="Sort descending")

    # ---------------- ls ----------------
    p_ls = subparsers.add_parser("ls", help="List local models (alias of 'list')")
    p_ls.add_argument(
        "--sort-by",
        choices=["name", "size", "modified", "id"],
        default="name",
        help="Sort models by column",
    )
    p_ls.add_argument(
        "--sort-asc", action="store_true", help="Sort ascending (default)"
    )
    p_ls.add_argument("--sort-desc", action="store_true", help="Sort descending")

    # ---------------- help ----------------
    subparsers.add_parser("help", help="Show this help message")

    # ---------------- blobs ----------------
    p_blobs = subparsers.add_parser(
        "blobs",
        help="Inspect blobs, manifests and orphans in the Ollama models directory.",
    )
    p_blobs.add_argument("--models-root", default="~/.ollama/models")
    p_blobs.add_argument("--as-csv", action="store_true", help="Output as CSV")
    p_blobs.add_argument(
        "-o", "--output", default="-", help="CSV output path (default: stdout)"
    )
    p_blobs.add_argument(
        "--delete-orphans", action="store_true", help="Delete orphan blobs"
    )
    p_blobs.add_argument(
        "--force", action="store_true", help="Do not ask before deleting"
    )
    p_blobs.add_argument(
        "--only-orphans", action="store_true", help="Show only orphans"
    )
    p_blobs.add_argument(
        "--sort-by-blob", action="store_true", help="Sort by blob name"
    )
    p_blobs.add_argument(
        "--sort-by-model", action="store_true", help="Sort by first model name"
    )
    p_blobs.add_argument(
        "--sort-by-size", action="store_true", help="Sort by size in bytes"
    )
    p_blobs.add_argument(
        "--sort-asc", action="store_true", help="Sort ascending (default)"
    )
    p_blobs.add_argument("--sort-desc", action="store_true", help="Sort descending")
    p_blobs.add_argument(
        "--format",
        choices=["mb", "gb"],
        default="mb",
        help="Format for human-readable size (default: mb)",
    )
    p_blobs.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    p_blobs.add_argument(
        "--columns",
        default="blob,models,size,is_orphan",
        help="Comma-separated list of columns: blob,models,size_bytes,size,is_orphan",
    )
    p_blobs.add_argument(
        "--progress",
        action="store_true",
        help="Show a simple progress bar while processing blobs",
    )
    p_blobs.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information (paths, blob count, etc.)",
    )
    p_blobs.add_argument(
        "--debug-blob",
        default="",
        help="Hash (without 'sha256-') to debug presence (e.g. 9d507a3...)",
    )

    # ---------------- models ----------------
    p_models = subparsers.add_parser(
        "models",
        help=(
            "List models with blob counts and total disk usage "
            "(based on manifests + blobs)."
        ),
    )
    p_models.add_argument("--models-root", default="~/.ollama/models")
    p_models.add_argument(
        "--format",
        choices=["mb", "gb"],
        default="mb",
        help="Format for human-readable size (default: mb)",
    )
    p_models.add_argument("--as-csv", action="store_true", help="Output as CSV")
    p_models.add_argument(
        "-o", "--output", default="-", help="CSV output path (default: stdout)"
    )
    p_models.add_argument(
        "--sort-by-size", action="store_true", help="Sort by total model size"
    )
    p_models.add_argument(
        "--sort-desc", action="store_true", help="Sort descending (default: asc)"
    )
    p_models.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )

    # Wire up default functions
    for name, func in [
        ("up", cmd_up),
        ("down", cmd_down),
        ("build", cmd_build_service),
        ("status", cmd_status),
        ("profiles", cmd_profiles),
        ("install-defaults", cmd_install_defaults),
        ("launch", cmd_launch_model),
        ("list-remote", remote.cmd_list_remote_models),
        ("shell", cmd_shell),
        ("update-models", cmd_update_models),
        ("list", cmd_list),
        ("ls", cmd_list),
        ("help", cmd_help),
        ("blobs", blobs.cmd_blobs),
        ("models", blobs.cmd_models),
        ("setup", cmd_setup),
        ("install-models", cmd_install_models),
    ]:
        p = subparsers.choices.get(name)
        if p:
            p.set_defaults(func=func)

    # Special handling for version
    p_ver = subparsers.choices.get("version")
    if p_ver:
        p_ver.set_defaults(func=lambda args: compose.run_ollama(["--version"]))

    return parser


def is_known_wrapper_command(argv: list[str]) -> bool:
    """Check if there is a local implementation of the command."""
    # Find the command (first non-option argument, or first argument if all are options)
    command = None
    for arg in argv:
        if not arg.startswith("-"):
            command = arg
            break
    if not command and argv:
        command = argv[0]
    return command in WRAPPER_COMMANDS


# ============================================================
#  Main
# ============================================================
def main() -> None:
    """Main entry point."""
    global DEBUG_ENABLED

    argv = sys.argv[1:]

    if "--debug" in argv:
        DEBUG_ENABLED = True

    # Translate option-like commands to internal commands in argv (only for the command argument itself)
    CMD_MAP = {
        "--up": "up",
        "--down": "down",
        "--build": "build",
        "--status": "status",
        "--profiles": "profiles",
        "--install-defaults": "install-defaults",
        "--launch": "launch",
        "--list-remote": "list-remote",
        "--shell": "shell",
        "--update-models": "update-models",
        "--blobs": "blobs",
        "--models": "models",
        "--setup": "setup",
        "--install-models": "install-models",
    }
    cmd_idx = -1
    for i, arg in enumerate(argv):
        if not arg.startswith("-") or arg in CMD_MAP:
            cmd_idx = i
            break
    if cmd_idx == -1 and argv:
        cmd_idx = 0

    if cmd_idx != -1 and argv[cmd_idx] in CMD_MAP:
        argv[cmd_idx] = CMD_MAP[argv[cmd_idx]]

    if argv and not is_known_wrapper_command(argv):
        # Find command name for debug print
        command = None
        for arg in argv:
            if not arg.startswith("-"):
                command = arg
                break
        if not command:
            command = argv[0]

        if DEBUG_ENABLED:
            print(
                f"DEBUG: unrecognized command '{command}', proxying to container.",
                file=sys.stderr,
            )
        container_argv = [arg for arg in argv if arg != "--debug"]
        compose.run_ollama(container_argv)
        return

    parser = build_parser()

    if not argv:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    if getattr(args, "debug", False):
        DEBUG_ENABLED = True

    args.func(args)


if __name__ == "__main__":
    main()
