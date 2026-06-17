#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any

from . import utils


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
    """Extract blob -> models mapping from manifest files.
    
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
    """Very relaxed hash extraction for filenames that do NOT start with 'sha256-'.

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
    """Return ALL blob hashes found for files in blobs_root.

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
#  Blob analysis command
# ============================================================
def cmd_blobs(args: Any) -> None:
    """Analyze blobs and manifests, find orphans."""
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
            utils.progress_bar(idx, total_blobs, prefix="Blobs: ")

        blob_file = blobs_root / f"sha256-{blob_hash}"
        models = sorted(blob_to_models.get(blob_hash, []))
        bsize = utils.size_bytes(blob_file)
        size_str = utils.format_size(bsize, args.format)

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
        import sys
        print("Error: no columns specified", file=sys.stderr)
        sys.exit(2)
    unknown = [c for c in columns if c not in all_cols]
    if unknown:
        import sys
        print(
            f"Error: unknown columns: {', '.join(unknown)}; "
            f"allowed: {', '.join(sorted(all_cols))}",
            file=sys.stderr,
        )
        sys.exit(2)

    # output
    if args.as_csv:
        utils.write_csv(rows, columns, args.output)
    else:
        utils.print_table(
            rows, columns, enable_color=(not args.no_color and utils.supports_color())
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
#  models aggregation command
# ============================================================
def cmd_models(args: Any) -> None:
    """Show models with total blob size and blob count, based on manifests + blobs."""
    root = Path(args.models_root).expanduser()
    manifest_root = root / "manifests" / "registry.ollama.ai"
    blobs_root = root / "blobs"

    blob_to_models = collect_blob_mappings(manifest_root)
    blobs = list_all_blobs(blobs_root)

    # Precompute blob sizes
    blob_sizes: dict[str, int] = {}
    for blob_hash in blobs:
        blob_file = blobs_root / f"sha256-{blob_hash}"
        blob_sizes[blob_hash] = utils.size_bytes(blob_file)

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
                "total_size": utils.format_size(total_b, args.format),
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
        utils.write_csv(rows, columns, args.output)
    else:
        utils.print_table(
            rows, columns, enable_color=(not args.no_color and utils.supports_color())
        )
