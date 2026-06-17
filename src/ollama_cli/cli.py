#!/usr/bin/env python3
import argparse
import contextlib
import csv
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any

from bs4 import BeautifulSoup, Tag
import requests

# ============================================================
#  Global configurations
# ============================================================
SERVICE = os.environ.get("OLLAMA_COMPOSE_SERVICE", "ollama")
PROJECT_NAME = os.environ.get("OLLAMA_PROJECT_NAME", "ai-tools-ollama")
DEBUG_ENABLED = os.environ.get("OLLAMA_DEBUG", "").lower() in {"1", "true", "yes", "on"}

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
}


# ============================================================
#  Model name cleaning
# ============================================================
def normalize_model_name(model_path: str) -> str:
    """Convert manifest path to a short model name (strip library/, cut at first /)."""
    if model_path.startswith("library/"):
        model_path = model_path[len("library/") :]
    return model_path.split("/", 1)[0]


# ============================================================
#  Blob → models mapping (from manifests)
# ============================================================
def collect_blob_mappings(manifest_root: Path) -> dict[str, set[str]]:
    """
    Returns:
        blob_to_models: blob_hash -> set(models)
    """
    blob_to_models: dict[str, set[str]] = {}

    if not manifest_root.exists():
        return blob_to_models

    for mf in manifest_root.rglob("*"):
        if not mf.is_file():
            continue

        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue

        raw_model_path = str(mf.relative_to(manifest_root))
        model_name = normalize_model_name(raw_model_path)

        def add_digest(digest: str | None, model_name=model_name):
            if isinstance(digest, str) and digest.startswith("sha256:"):
                blob_hash = digest.split("sha256:", 1)[1]
                blob_to_models.setdefault(blob_hash, set()).add(model_name)

        cfg = data.get("config")
        if isinstance(cfg, dict):
            add_digest(cfg.get("digest"))

        for layer in data.get("layers", []):
            if isinstance(layer, dict):
                add_digest(layer.get("digest"))

    return blob_to_models


# ============================================================
#  Ensure *all* files in blobs directory are processed
# ============================================================
def extract_blob_hash_relaxed(name: str) -> str | None:
    """
    Very relaxed hash extraction for filenames that do NOT start with 'sha256-'.

    Used as a fallback only; any 'sha256-...' file is always included directly.
    """
    n = name.lower()
    n = n.split(".", 1)[0]  # strip extensions

    if n.startswith("sha256"):
        n = n[len("sha256") :]

    if len(n) < 40 or len(n) > 128:
        return None
    if not all(c in "0123456789abcdef" for c in n):
        return None

    return n


def list_all_blobs(blobs_root: Path) -> list[str]:
    """
    Return ALL blob hashes found for files in blobs_root.

    Rules:
    - If filename starts with 'sha256-': we *always* take everything after 'sha256-'
      as the hash, no validation.
    - Otherwise, we try a relaxed extractor which attempts to parse a hex-ish hash.
    """
    blobs: set[str] = set()

    if not blobs_root.exists():
        return []

    for f in blobs_root.iterdir():
        if not f.is_file():
            continue
        name = f.name

        if name.startswith("sha256-") and len(name) > len("sha256-"):
            blobs.add(name[len("sha256-") :])
            continue

        h = extract_blob_hash_relaxed(name)
        if h:
            blobs.add(h)

    return sorted(blobs)


# ============================================================
#  Helpers
# ============================================================
def size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def format_size(b: int, unit: str) -> str:
    if unit == "gb":
        return f"{b / (1024**3):.2f} GB"
    return f"{b / (1024**2):.2f} MB"


def supports_color() -> bool:
    return os.isatty(1)


def colorize(text: str, color: str, enable: bool) -> str:
    return f"\033[{color}m{text}\033[0m" if enable else text


# ============================================================
#  Table / CSV output
# ============================================================
def print_table(rows: list[dict], columns: list[str], enable_color: bool) -> None:
    if not rows:
        print("No rows.")
        return

    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns}

    header_line = "  ".join(c.ljust(widths[c]) for c in columns)
    print(colorize(header_line, "1;37", enable_color))
    print("-" * len(header_line))

    for r in rows:
        is_orphan = r.get("is_orphan") == "yes"
        parts = []
        for c in columns:
            val = str(r[c]).ljust(widths[c])
            if is_orphan:
                val = colorize(val, "31", enable_color)
            parts.append(val)
        print("  ".join(parts))


def write_csv(rows: list[dict], columns: list[str], out_path: str) -> None:
    if out_path in ("-", ""):
        writer = csv.writer(sys.stdout)
        writer.writerow(columns)
        for r in rows:
            writer.writerow([r[c] for c in columns])
    else:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for r in rows:
                writer.writerow([r[c] for c in columns])


# ============================================================
#  Progress bar
# ============================================================
def progress_bar(current: int, total: int, prefix: str = "") -> None:
    if total <= 0:
        return
    width = 30
    ratio = current / total
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{prefix}[{bar}] {current}/{total}", end="", flush=True)


# ============================================================
#  Docker Compose wrapper helpers
# ============================================================
def resolve_compose_dir() -> Path:
    env_dir = os.environ.get("OLLAMA_COMPOSE_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    hardcoded = Path(
        "/Users/Shared/CLOUD/Projekte/CLIs/ollama-cli/DOCKER/ollama-wrapper"
    )
    if hardcoded.exists() and (hardcoded / "docker-compose.yaml").is_file():
        return hardcoded

    try:
        source_dir = Path(__file__).resolve().parents[2] / "DOCKER" / "ollama-wrapper"
        if source_dir.exists() and (source_dir / "docker-compose.yaml").is_file():
            return source_dir
    except Exception:
        pass

    try:
        bin_relative = Path(sys.argv[0]).resolve().parent / "DOCKER" / "ollama-wrapper"
        if bin_relative.exists() and (bin_relative / "docker-compose.yaml").is_file():
            return bin_relative
    except Exception:
        pass

    return Path.cwd()


COMPOSE_DIR = resolve_compose_dir()
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yaml"
COMPOSE_BASE_CMD = ["docker", "compose", "-p", PROJECT_NAME, "-f", str(COMPOSE_FILE)]


def ensure_compose_file() -> None:
    if not COMPOSE_FILE.is_file():
        print(
            f"ERROR: docker-compose.yaml not found at: {COMPOSE_FILE}", file=sys.stderr
        )
        print(
            "Hint: set OLLAMA_COMPOSE_DIR to the folder containing docker-compose.yaml",
            file=sys.stderr,
        )
        sys.exit(2)


def is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    if DEBUG_ENABLED:
        print(
            f"DEBUG: run_cmd: {' '.join(cmd)} capture_output={capture_output}",
            file=sys.stderr,
        )
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def exec_cmd(cmd: list[str]) -> None:
    if DEBUG_ENABLED:
        print(f"DEBUG: exec_cmd: {' '.join(cmd)}", file=sys.stderr)
    os.execvp(cmd[0], cmd)


def compose_build_cmd(*args: str) -> list[str]:
    return [*COMPOSE_BASE_CMD, *args]


def compose_exec_cmd(command: list[str]) -> list[str]:
    cmd = [*COMPOSE_BASE_CMD, "exec"]
    if not is_tty():
        cmd.append("-T")
    cmd.append(SERVICE)
    cmd.extend(command)
    return cmd


def compose_exec(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        compose_exec_cmd(command), check=check, capture_output=capture_output
    )


def compose_exec_or_exec(command: list[str]) -> None:
    exec_cmd(compose_exec_cmd(command))


def is_known_wrapper_command(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in WRAPPER_COMMANDS


def ensure_service_exists() -> None:
    ensure_compose_file()
    result = run_cmd(
        compose_build_cmd("config", "--services"),
        capture_output=True,
        check=True,
    )
    services = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if SERVICE not in services:
        print(
            f"ERROR: service '{SERVICE}' not found in compose file: {COMPOSE_FILE}",
            file=sys.stderr,
        )
        print("Available services:", file=sys.stderr)
        for service in sorted(services):
            print(service, file=sys.stderr)
        sys.exit(2)


def is_service_running() -> bool:
    ensure_compose_file()
    result = run_cmd(
        compose_build_cmd("ps", "-q", SERVICE),
        capture_output=True,
        check=True,
    )
    return bool(result.stdout.strip())


def ensure_service_running() -> None:
    ensure_service_exists()
    if not is_service_running():
        run_cmd(compose_build_cmd("up", "-d", SERVICE), check=True)


def run_ollama(args: list[str]) -> None:
    ensure_service_running()
    compose_exec_or_exec(["ollama", *args])


def ensure_model_exists(model: str) -> bool:
    ensure_service_running()
    result = compose_exec(["ollama", "list"], check=True, capture_output=True)
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
    if ensure_model_exists(model):
        return
    print(f"Model '{model}' is not available locally. Pulling it now...")
    compose_exec(["ollama", "pull", model], check=True)


def get_default_models() -> list[str]:
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
    ensure_service_running()
    response = compose_exec(["ollama", "list"], check=True, capture_output=True)
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


def parse_size_to_bytes(size_str: str) -> int:
    try:
        parts = size_str.strip().split()
        if len(parts) < 2:
            return 0
        val = float(parts[0])
        unit = parts[1].lower()
        if "gb" in unit:
            return int(val * 1024 * 1024 * 1024)
        if "mb" in unit:
            return int(val * 1024 * 1024)
        if "kb" in unit:
            return int(val * 1024)
        return int(val)
    except Exception:
        return 0


def parse_relative_time_to_seconds(time_str: str) -> int:
    try:
        s = time_str.lower().strip()
        if "ago" in s:
            s = s.replace("ago", "").strip()
        parts = s.split()
        if len(parts) < 2:
            return 0
        val = float(parts[0])
        unit = parts[1]
        if "second" in unit:
            factor = 1
        elif "minute" in unit:
            factor = 60
        elif "hour" in unit:
            factor = 3600
        elif "day" in unit:
            factor = 86400
        elif "week" in unit:
            factor = 86400 * 7
        elif "month" in unit:
            factor = 86400 * 30
        elif "year" in unit:
            factor = 86400 * 365
        else:
            factor = 1
        return int(val * factor)
    except Exception:
        return 9999999999


def extract_models(
    html: str,
    *,
    limit: int,
    with_description: bool,
    filter_capabilities: list[str] | None = None,
    sort_by: str = "order",
) -> None:
    soup = BeautifulSoup(html, "html.parser")

    columns = ["model_name", "capabilities", "sizes", "updated"]
    if with_description:
        columns.append("description")

    rows: list[dict[str, Any]] = []
    normalized_filter_capabilities = {
        item.strip().lower() for item in (filter_capabilities or []) if item.strip()
    }

    order = 1

    for li in soup.find_all("li", attrs={"x-test-model": True}):
        if not isinstance(li, Tag):
            continue

        name_div = li.find("div", attrs={"title": True})
        model_name = (
            name_div.get("title", "").strip() if isinstance(name_div, Tag) else "N/A"
        )

        desc_p = li.find("p", class_="max-w-lg")
        description = desc_p.get_text(strip=True) if isinstance(desc_p, Tag) else ""

        capabilities: list[str] = []
        container = li.find("div", class_="flex flex-wrap space-x-2")
        if isinstance(container, Tag):
            for span in container.find_all(
                "span", class_="inline-flex", recursive=False
            ):
                if not isinstance(span, Tag):
                    continue
                if span.has_attr("x-test-size"):
                    continue
                text = span.get_text(strip=True)
                if text:
                    capabilities.append(text)

        sizes = [
            span.get_text(strip=True)
            for span in li.find_all("span", attrs={"x-test-size": True})
            if isinstance(span, Tag)
        ]

        update_span = li.find("span", attrs={"x-test-updated": True})
        updated = (
            update_span.get_text(strip=True) if isinstance(update_span, Tag) else "N/A"
        )

        capability_set = {cap.lower() for cap in capabilities}
        if normalized_filter_capabilities and not capability_set.intersection(
            normalized_filter_capabilities
        ):
            continue

        rows.append(
            {
                "order": order,
                "model_name": model_name,
                "capabilities": capabilities,
                "sizes": sizes,
                "updated": updated,
                "description": description,
            }
        )
        order += 1

    if not rows:
        print("No remote models found.")
        return

    def get_row_order(row: dict[str, Any], fallback: int) -> int:
        value = row.get("order")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return fallback

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[object, ...]:
        fallback_index, row = item
        model_name = str(row.get("model_name", "")).lower()
        capabilities = [str(x).lower() for x in row.get("capabilities", [])]
        sizes = [str(x).lower() for x in row.get("sizes", [])]
        updated = str(row.get("updated", "")).lower()
        order_value = get_row_order(row, fallback_index)

        if sort_by == "capability":
            return (",".join(capabilities), model_name, order_value)

        if sort_by == "size":
            return (len(sizes), ",".join(sizes), model_name, order_value)

        if sort_by == "date":
            return (updated, model_name, order_value)

        if sort_by == "name":
            return (model_name, order_value)

        return (order_value,)

    limited_rows = rows[:limit] if limit > 0 else rows

    limited_rows = [
        row for _, row in sorted(enumerate(limited_rows, start=1), key=sort_key)
    ]

    printable_rows: list[list[str]] = []
    for row in limited_rows:
        printable_row = [
            str(row["model_name"]),
            ", ".join(row["capabilities"]),
            ", ".join(row["sizes"]),
            str(row["updated"]),
        ]
        if with_description:
            printable_row.append(str(row["description"]))
        printable_rows.append(printable_row)

    col_count = len(columns)
    col_widths = [
        max(len(columns[i]), *(len(str(row[i])) for row in printable_rows))
        for i in range(col_count)
    ]

    if with_description:
        header = "  ".join(
            str(item).ljust(col_widths[i]) for i, item in enumerate(columns[:-1])
        )
        print(header)
        print()
        for row in printable_rows:
            print(
                "  ".join(
                    str(item).ljust(col_widths[i]) for i, item in enumerate(row[:-1])
                )
            )
            print(row[-1])
            print()
    else:
        print(
            "  ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(columns))
        )
        for row in printable_rows:
            print(
                "  ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(row))
            )


# ============================================================
#  Subcommands handlers
# ============================================================
def cmd_up(args: argparse.Namespace) -> None:
    run_cmd(compose_build_cmd("up", "-d"), check=True)


def cmd_down(args: argparse.Namespace) -> None:
    run_cmd(compose_build_cmd("down"), check=True)


def cmd_build_service(args: argparse.Namespace) -> None:
    run_cmd(["docker", "pull", "ollama/ollama:latest"], check=True)
    run_cmd(compose_build_cmd("build"), check=True)


def cmd_status(args: argparse.Namespace) -> None:
    ensure_compose_file()
    print(f"Compose file : {COMPOSE_FILE}")
    print(f"Project name : {PROJECT_NAME}")
    print(f"Service      : {SERVICE}")
    print()

    print("Container status:")
    with contextlib.suppress(subprocess.CalledProcessError):
        run_cmd(compose_build_cmd("ps", SERVICE), check=True)
    print()

    if is_service_running():
        print("Ollama models:")
        with contextlib.suppress(subprocess.CalledProcessError):
            compose_exec(["ollama", "list"], check=True)
        print()
        print("Running models:")
        with contextlib.suppress(subprocess.CalledProcessError):
            compose_exec(["ollama", "ps"], check=True)
    else:
        print(f"Service '{SERVICE}' is not running.")


def cmd_profiles(args: argparse.Namespace) -> None:
    print("Available launch profiles:")
    for name, model in LAUNCH_MODELS.items():
        print(f"  {name:<10} -> {model}")


def cmd_install_defaults(args: argparse.Namespace) -> None:
    ensure_service_running()
    defaults = get_default_models()
    print(f"Pulling default models into Ollama volume for service '{SERVICE}'...")
    print("Models:")
    for model in defaults:
        print(f"  {model}")
    print()

    for model in defaults:
        print(f"==> ollama pull {model}")
        compose_exec(["ollama", "pull", model], check=True)
        print()

    print("Done. Current tags:")
    with contextlib.suppress(subprocess.CalledProcessError):
        compose_exec(["ollama", "list"], check=True)


def cmd_launch_model(args: argparse.Namespace) -> None:
    profile = args.profile
    prompt_parts = args.prompt
    model = LAUNCH_MODELS.get(profile)
    if not model:
        print(f"ERROR: unknown launch profile '{profile}'", file=sys.stderr)
        print("Run 'profiles' to see available profiles.", file=sys.stderr)
        sys.exit(2)

    ensure_service_running()
    ensure_model_pulled(model)

    print(f"Launching profile '{profile}' with model '{model}'...")

    cmd = ["ollama", "run", model]
    if prompt_parts:
        cmd.append(" ".join(prompt_parts))
    compose_exec_or_exec(cmd)


def cmd_list_remote_models(args: argparse.Namespace) -> None:
    response = requests.get("https://ollama.com/library", timeout=20)
    response.raise_for_status()
    extract_models(
        response.text,
        limit=args.limit,
        with_description=args.with_description,
        filter_capabilities=args.filter_capabilities,
        sort_by=args.sort_by,
    )


def cmd_shell(args: argparse.Namespace) -> None:
    ensure_service_running()
    compose_exec_or_exec(["bash"])


def cmd_update_models(args: argparse.Namespace) -> None:
    models = get_list_of_installed_models()
    for model in models:
        print(f"Update '{model}'")
        compose_exec(["ollama", "pull", model], check=True)


def cmd_list(args: argparse.Namespace) -> None:
    ensure_service_running()
    result = compose_exec(["ollama", "list"], check=True, capture_output=True)

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
                    "size_bytes": parse_size_to_bytes(parts[2]),
                    "modified_seconds": parse_relative_time_to_seconds(parts[3]),
                }
            )
        elif len(parts) == 3:
            rows.append(
                {
                    "name": parts[0],
                    "id": parts[1],
                    "size": parts[2],
                    "modified": "unknown",
                    "size_bytes": parse_size_to_bytes(parts[2]),
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
        f"{'NAME'.ljust(widths['NAME'])}  "
        f"{'ID'.ljust(widths['ID'])}  "
        f"{'SIZE'.ljust(widths['SIZE'])}  "
        f"{'MODIFIED'.ljust(widths['MODIFIED'])}"
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
    parser = build_parser()
    parser.print_help()
    sys.exit(0)


# ============================================================
#  blobs subcommand (your original tool)
# ============================================================
def cmd_blobs(args: argparse.Namespace) -> None:
    root = Path(args.models_root).expanduser()
    manifest_root = root / "manifests" / "registry.ollama.ai"
    blobs_root = root / "blobs"

    if args.debug:
        print(f"DEBUG: models_root   = {root}")
        print(f"DEBUG: manifest_root = {manifest_root}")
        print(f"DEBUG: blobs_root    = {blobs_root}")

    blob_to_models = collect_blob_mappings(manifest_root)
    blobs = list_all_blobs(blobs_root)

    if args.debug:
        print(f"DEBUG: total blobs found in blobs/ = {len(blobs)}")
        if args.debug_blob:
            hb = args.debug_blob.lower()
            in_list = any(b.startswith(hb) for b in blobs)
            print(f"DEBUG: debug-blob '{hb}' present in blobs list: {in_list}")

    rows: list[dict] = []
    orphan_files: list[Path] = []

    total_blobs = len(blobs)
    if args.progress and total_blobs > 0:
        print(f"Processing {total_blobs} blobs...")

    for idx, blob_hash in enumerate(blobs, start=1):
        if args.progress and total_blobs > 0:
            progress_bar(idx, total_blobs, prefix="Blobs: ")

        blob_file = blobs_root / f"sha256-{blob_hash}"
        models = sorted(blob_to_models.get(blob_hash, []))
        bsize = size_bytes(blob_file)
        size_str = format_size(bsize, args.format)

        is_orphan = len(models) == 0
        if is_orphan:
            orphan_files.append(blob_file)

        rows.append(
            {
                "blob": f"sha256-{blob_hash}",
                "models": "|".join(models),
                "size_bytes": bsize,
                "size": size_str,
                "is_orphan": "yes" if is_orphan else "no",
            }
        )

    if args.progress and total_blobs > 0:
        print()  # newline after progress bar

    # filter only-orphans
    if args.only_orphans:
        rows = [r for r in rows if r["is_orphan"] == "yes"]

    # sorting
    reverse_sort = args.sort_desc
    if args.sort_by_blob:
        rows.sort(key=lambda r: r["blob"], reverse=reverse_sort)
    elif args.sort_by_model:
        rows.sort(
            key=lambda r: (r["models"] == "", r["models"], r["blob"]),
            reverse=reverse_sort,
        )
    elif args.sort_by_size:
        rows.sort(key=lambda r: r["size_bytes"], reverse=reverse_sort)

    # columns
    all_cols = {"blob", "models", "size_bytes", "size", "is_orphan"}
    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    if not columns:
        print("Error: no columns specified", file=sys.stderr)
        sys.exit(2)
    unknown = [c for c in columns if c not in all_cols]
    if unknown:
        print(
            f"Error: unknown columns: {', '.join(unknown)}; "
            f"allowed: {', '.join(sorted(all_cols))}",
            file=sys.stderr,
        )
        sys.exit(2)

    # output
    if args.as_csv:
        write_csv(rows, columns, args.output)
    else:
        print_table(
            rows, columns, enable_color=(not args.no_color and supports_color())
        )

    # delete orphans
    if args.delete_orphans:
        if not orphan_files:
            print("\nNo orphan blobs found.")
            return

        print("\nOrphan blobs to delete:")
        for f in orphan_files:
            print("  blobs/" + f.name)

        if not args.force:
            confirm = input("Delete? (yes/no) ").strip().lower()
            if confirm != "yes":
                print("Aborted.")
                return

        for f in orphan_files:
            try:
                f.unlink()
                print("Deleted: blobs/" + f.name)
            except Exception as e:
                print("Failed:", f, e)

        print("Done.")


# ============================================================
#  models subcommand (aggregate per model)
# ============================================================
def cmd_models(args: argparse.Namespace) -> None:
    """
    Show models with total blob size and blob count, based on manifests + blobs.
    """
    root = Path(args.models_root).expanduser()
    manifest_root = root / "manifests" / "registry.ollama.ai"
    blobs_root = root / "blobs"

    blob_to_models = collect_blob_mappings(manifest_root)
    blobs = list_all_blobs(blobs_root)

    # Precompute blob sizes
    blob_sizes: dict[str, int] = {}
    for blob_hash in blobs:
        blob_file = blobs_root / f"sha256-{blob_hash}"
        blob_sizes[blob_hash] = size_bytes(blob_file)

    # Aggregate per model
    model_info: dict[str, dict[str, object]] = {}
    for blob_hash, models in blob_to_models.items():
        size_b = blob_sizes.get(blob_hash, 0)
        for m in models:
            info = model_info.setdefault(
                m, {"model": m, "blob_count": 0, "total_bytes": 0}
            )
            info["blob_count"] = int(info["blob_count"]) + 1
            info["total_bytes"] = int(info["total_bytes"]) + size_b

    # Convert to rows
    rows: list[dict] = []
    for m, info in model_info.items():
        total_b = int(info["total_bytes"])
        rows.append(
            {
                "model": m,
                "blob_count": int(info["blob_count"]),
                "total_bytes": total_b,
                "total_size": format_size(total_b, args.format),
            }
        )

    # sorting
    reverse = args.sort_desc
    if args.sort_by_size:
        rows.sort(key=lambda r: r["total_bytes"], reverse=reverse)
    else:
        rows.sort(key=lambda r: r["model"], reverse=reverse)

    columns = ["model", "blob_count", "total_size", "total_bytes"]
    if args.as_csv:
        write_csv(rows, columns, args.output)
    else:
        print_table(
            rows, columns, enable_color=(not args.no_color and supports_color())
        )


# ============================================================
#  Argument parsing
# ============================================================
def get_install_source() -> str:
    import os

    if hasattr(sys, "oxidized"):
        return "pyoxidizer"
    elif getattr(sys, "frozen", False):
        return "pyinstaller"

    argv0 = sys.argv[0] if (sys.argv and sys.argv[0] is not None) else ""
    if "SHIV_ENTRY_POINT" in os.environ or ".pyz" in argv0:
        return "shiv"
    else:
        return "source"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ollama-cli",
        description=(
            "Extended Ollama CLI helper and Docker Compose wrapper.\n\n"
            "Wrapper commands:\n"
            "  - up               : Start the Ollama service stack\n"
            "  - down             : Stop the Ollama service stack\n"
            "  - build            : Pull base image and rebuild the Ollama service\n"
            "  - status           : Show container and model status\n"
            "  - profiles         : List launch profiles\n"
            "  - install-defaults : Pull default model set into the Ollama volume\n"
            "  - launch           : Launch a predefined profile\n"
            "  - list-remote      : List models from the Ollama library website\n"
            "  - shell            : Open a shell inside the Ollama container\n"
            "  - update-models    : Pull the latest version for all installed models\n"
            "  - list / ls        : List local models with sort options\n"
            "  - blobs            : Inspect blobs / manifests / orphans\n"
            "  - models           : List models with blob counts and total sizes\n\n"
            "Other commands are proxied directly to 'ollama' in the container."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"ollama-cli version 1.0.2 ({get_install_source()})",
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
        default="order",
        help="Sort output by capability, size, date, name, or keep original order",
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
        ("list-remote", cmd_list_remote_models),
        ("shell", cmd_shell),
        ("update-models", cmd_update_models),
        ("list", cmd_list),
        ("ls", cmd_list),
        ("help", cmd_help),
        ("blobs", cmd_blobs),
        ("models", cmd_models),
    ]:
        p = subparsers.choices.get(name)
        if p:
            p.set_defaults(func=func)

    # Special handling for version
    p_ver = subparsers.choices.get("version")
    if p_ver:
        p_ver.set_defaults(func=lambda args: run_ollama(["--version"]))

    return parser


# ============================================================
#  Main
# ============================================================
def main() -> None:
    global DEBUG_ENABLED

    argv = sys.argv[1:]

    if "--debug" in argv:
        DEBUG_ENABLED = True

    if argv and not is_known_wrapper_command(argv):
        if DEBUG_ENABLED:
            print(
                f"DEBUG: unrecognized command '{argv[0]}', proxying to container.",
                file=sys.stderr,
            )
        run_ollama(argv)
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
