#!/usr/bin/env python3
import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Optional


# ------------------------------------------------------------
# Model name cleaning
# ------------------------------------------------------------
def normalize_model_name(model_path: str) -> str:
    """Convert manifest path to a short model name (strip library/, cut at first /)."""
    if model_path.startswith("library/"):
        model_path = model_path[len("library/"):]
    return model_path.split("/", 1)[0]


# ------------------------------------------------------------
# Blob → models mapping (from manifests)
# ------------------------------------------------------------
def collect_blob_mappings(manifest_root: Path) -> Dict[str, Set[str]]:
    """
    Returns:
        blob_to_models: blob_hash -> set(models)
    """
    blob_to_models: Dict[str, Set[str]] = {}

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

        def add_digest(digest: Optional[str]):
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


# ------------------------------------------------------------
# Ensure *all* files in blobs directory are processed
# ------------------------------------------------------------
def extract_blob_hash_relaxed(name: str) -> Optional[str]:
    """
    Very relaxed hash extraction for filenames that do NOT start with 'sha256-'.

    Used as a fallback only; any 'sha256-...' file is always included directly.
    """
    n = name.lower()

    # strip possible extensions
    n = n.split(".", 1)[0]

    # strip optional 'sha256' prefix without dash
    if n.startswith("sha256"):
        n = n[len("sha256"):]

    # now expect a hex-ish string
    if len(n) < 40 or len(n) > 128:
        return None
    if not all(c in "0123456789abcdef" for c in n):
        return None

    return n


def list_all_blobs(blobs_root: Path) -> List[str]:
    """
    Return ALL blob hashes found for files in blobs_root.

    Rules:
    - If filename starts with 'sha256-': we *always* take everything after 'sha256-'
      as the hash, no validation.
    - Otherwise, we try a relaxed extractor which attempts to parse a hex-ish hash.
    """
    blobs: Set[str] = set()

    if not blobs_root.exists():
        return []

    for f in blobs_root.iterdir():
        if not f.is_file():
            continue
        name = f.name

        # Normal ollama blobs: sha256-<hash>...
        if name.startswith("sha256-") and len(name) > len("sha256-"):
            blobs.add(name[len("sha256-"):])
            continue

        # Fallback for any non-standard names
        h = extract_blob_hash_relaxed(name)
        if h:
            blobs.add(h)

    return sorted(blobs)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def format_size(b: int, unit: str) -> str:
    if unit == "gb":
        return f"{b / (1024 ** 3):.2f} GB"
    return f"{b / (1024 ** 2):.2f} MB"


def supports_color() -> bool:
    return os.isatty(1)


def colorize(text: str, color: str, enable: bool) -> str:
    return f"\033[{color}m{text}\033[0m" if enable else text


# ------------------------------------------------------------
# Output
# ------------------------------------------------------------
def print_table(rows: List[dict], columns: List[str], enable_color: bool) -> None:
    if not rows:
        print("No blobs found.")
        return

    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns}

    header_line = "  ".join(c.ljust(widths[c]) for c in columns)
    print(colorize(header_line, "1;37", enable_color))
    print("-" * len(header_line))

    for r in rows:
        is_orphan = (r.get("is_orphan") == "yes")
        parts = []
        for c in columns:
            val = str(r[c]).ljust(widths[c])
            if is_orphan:
                val = colorize(val, "31", enable_color)
            parts.append(val)
        print("  ".join(parts))


def write_csv(rows: List[dict], columns: List[str], out_path: str) -> None:
    if out_path in ("-", ""):
        writer = csv.writer(os.sys.stdout)
        close = False
    else:
        f = open(out_path, "w", newline="", encoding="utf-8")
        writer = csv.writer(f)
        close = True

    writer.writerow(columns)
    for r in rows:
        writer.writerow([r[c] for c in columns])

    if close:
        f.close()


# ------------------------------------------------------------
# Progress bar (simple text)
# ------------------------------------------------------------
def progress_bar(current: int, total: int, prefix: str = "") -> None:
    if total <= 0:
        return
    width = 30
    ratio = current / total
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{prefix}[{bar}] {current}/{total}", end="", flush=True)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Ollama blobs and model mappings.")
    parser.add_argument("--models-root", default="~/.ollama/models")

    parser.add_argument("--as-csv", action="store_true")
    parser.add_argument("-o", "--output", default="-")

    parser.add_argument("--delete-orphans", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only-orphans", action="store_true")

    parser.add_argument("--sort-by-blob", action="store_true")
    parser.add_argument("--sort-by-model", action="store_true")
    parser.add_argument("--sort-by-size", action="store_true")

    parser.add_argument("--sort-asc", action="store_true", help="Sort ascending (default)")
    parser.add_argument("--sort-desc", action="store_true", help="Sort descending")

    parser.add_argument("--format", choices=["mb", "gb"], default="mb")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument(
        "--columns",
        default="blob,models,size,is_orphan",
        help="Comma-separated list of columns to show "
             "(default: blob,models,size_bytes,size,is_orphan)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show a simple progress bar while processing blobs",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information (paths, blob count, etc.)",
    )
    parser.add_argument(
        "--debug-blob",
        default="",
        help="Hash (without 'sha256-') to debug presence (e.g. 9d507a3...)",
    )

    args = parser.parse_args()

    # validate columns
    all_cols = {"blob", "models", "size_bytes", "size", "is_orphan"}
    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    if not columns:
        parser.error("No columns specified in --columns")
    unknown = [c for c in columns if c not in all_cols]
    if unknown:
        parser.error(
            f"Unknown columns: {', '.join(unknown)}. "
            f"Allowed: {', '.join(sorted(all_cols))}"
        )

    # sort validation
    sort_flags = [args.sort_by_blob, args.sort_by_model, args.sort_by_size]
    if sum(sort_flags) > 1:
        parser.error("Only one --sort-by option allowed")

    if args.sort_asc and args.sort_desc:
        parser.error("Choose only one: --sort-asc or --sort-desc")

    reverse_sort = args.sort_desc

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

    rows: List[dict] = []
    orphan_files: List[Path] = []

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

        rows.append({
            "blob": f"sha256-{blob_hash}",
            "models": "|".join(models),
            "size_bytes": bsize,
            "size": size_str,
            "is_orphan": "yes" if is_orphan else "no",
        })

    if args.progress and total_blobs > 0:
        print()  # newline after progress bar

    # filter only-orphans
    if args.only_orphans:
        rows = [r for r in rows if r["is_orphan"] == "yes"]

    # sorting
    if args.sort_by_blob:
        rows.sort(key=lambda r: r["blob"], reverse=reverse_sort)
    elif args.sort_by_model:
        rows.sort(key=lambda r: (r["models"] == "", r["models"], r["blob"]), reverse=reverse_sort)
    elif args.sort_by_size:
        rows.sort(key=lambda r: r["size_bytes"], reverse=reverse_sort)

    # output
    if args.as_csv:
        write_csv(rows, columns, args.output)
    else:
        print_table(rows, columns, enable_color=(not args.no_color and supports_color()))

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


if __name__ == "__main__":
    main()
