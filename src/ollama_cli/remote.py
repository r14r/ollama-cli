import re
import sys
import os
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from . import utils

def debug_print(msg: str) -> None:
    if os.environ.get("OLLAMA_DEBUG", "").lower() in {"1", "true", "yes", "on"}:
        print(f"DEBUG: {msg}", file=sys.stderr, flush=True)

ANSI_ESCAPE = re.compile(r'\033\[[0-9;]*m')

def clean_len(s: str) -> int:
    """Get visible length of a string, ignoring ANSI escape sequences."""
    return len(ANSI_ESCAPE.sub('', s))

def ljust_ansi(s: str, width: int) -> str:
    """Left justify a string while ignoring ANSI escape sequences."""
    visible_len = clean_len(s)
    padding = max(0, width - visible_len)
    return s + (" " * padding)


def parse_parameter_size(size_str: str) -> float | None:
    """Parse remote parameter size string (e.g. '8b' -> 8.0, '270m' -> 0.27)."""
    s = size_str.lower().strip()
    try:
        if s.endswith("b"):
            return float(s[:-1])
        if s.endswith("m"):
            return float(s[:-1]) / 1000.0
        return float(s)
    except ValueError:
        return None


def get_local_models() -> list[dict[str, Any]]:
    """Get list of all installed models with names and sizes in bytes."""
    debug_print("Checking local Ollama service and listing models...")
    try:
        from . import compose
        if not compose.is_service_running():
            debug_print("Local Ollama service is not running.")
            return []
        debug_print("Executing 'ollama list' inside the local container...")
        response = compose.compose_exec(["ollama", "list"], check=True, capture_output=True)
        debug_print("Successfully obtained local models list.")
        models_info = []
        lines = response.stdout.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if i == 0 and line.startswith("NAME"):
                continue
            # Split by 2 or more spaces to preserve columns
            parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
            if len(parts) >= 3:
                name = parts[0]
                size_str = parts[2]
                models_info.append({
                    "name": name,
                    "size_str": size_str,
                    "size_bytes": utils.parse_size_to_bytes(size_str)
                })
        return models_info
    except Exception:
        return []


def is_size_installed(remote_model_name: str, size_tag: str, local_models: list[dict[str, Any]]) -> bool:
    """Check if a remote size is installed locally (supports exact and parameter-size matches)."""
    remote_base = remote_model_name.lower()
    size_tag_lower = size_tag.lower()
    candidate_full_name = f"{remote_base}:{size_tag_lower}"

    # First pass: Exact name and tag match
    for lm in local_models:
        if lm["name"].lower() == candidate_full_name:
            return True

    # Second pass: Size match if local name contains "latest"
    for lm in local_models:
        lm_name = lm["name"].lower()
        parts = lm_name.split(":", 1)
        lm_base = parts[0]

        if lm_base == remote_base and "latest" in lm_name:
            params = parse_parameter_size(size_tag_lower)
            if params is not None and params > 0:
                local_size_gb = lm["size_bytes"] / (1024 ** 3)
                ratio = local_size_gb / params
                if 0.4 <= ratio <= 1.4:
                    return True

    return False


# ============================================================
#  Remote library operations
# ============================================================
def extract_models(
    html: str,
    *,
    limit: int,
    with_description: bool,
    filter_capabilities: list[str] | None = None,
    sort_by: str = "order",
    force: bool = False,
) -> None:
    """Extract and display models from Ollama library HTML, fetching tag-level details."""
    from pathlib import Path
    import time

    soup = BeautifulSoup(html, "html.parser")

    columns = ["model_name", "capabilities", "sizes", "usage", "updated"]
    if with_description:
        columns.append("description")

    # Target tag suffixes we want to extract
    TARGET_TAGS = {"latest", "cloud", "e2b", "e4b", "12b", "26b", "31b", "vision", "tools", "thinking", "audio"}

    base_models: list[dict[str, Any]] = []

    # 1. Parse base models from the library main page
    for li in soup.find_all("li", attrs={"x-test-model": True}):
        if not isinstance(li, Tag):
            continue

        name_div = li.find("div", attrs={"title": True})
        model_name = (
            name_div.get("title", "").strip() if isinstance(name_div, Tag) else "N/A"
        )
        if model_name == "N/A":
            continue

        desc_p = li.find("p", class_="max-w-lg")
        description = desc_p.get_text(strip=True) if isinstance(desc_p, Tag) else ""

        # Parse capabilities from the base card
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
                text = span.get_text(strip=True).lower()
                if text:
                    capabilities.append(text)

        base_models.append({
            "model_name": model_name,
            "description": description,
            "capabilities": capabilities,
        })

    # 2. Fetch tags for each base model
    tags_rows: list[dict[str, Any]] = []
    import requests
    session = requests.Session()

    print("Loading tag details...", flush=True)

    cache_dir = Path.home() / ".ollama-cli" / "cache"
    debug_print(f"Using cache directory: {cache_dir}")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        debug_print(f"Error creating cache directory: {e}")

    order = 1
    for bm in base_models:
        model_name = bm["model_name"]
        url = f"https://ollama.com/library/{model_name}/tags"
        cache_file = cache_dir / f"{model_name}.html"
        json_file = cache_dir / f"{model_name}.json"
        html_to_parse = None

        # Try cache
        if not force and cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                # 24 hours cache validity
                if time.time() - mtime < 86400:
                    debug_print(f"Cache hit (fresh) for model '{model_name}' tags from {cache_file}")
                    html_to_parse = cache_file.read_text(encoding="utf-8")
                else:
                    debug_print(f"Cache expired for model '{model_name}' tags (older than 24 hours)")
            except Exception as e:
                debug_print(f"Error reading cache file for '{model_name}': {e}")

        if html_to_parse is None:
            try:
                debug_print(f"Downloading model tags from {url}...")
                resp = session.get(url, timeout=15)
                if resp.status_code == 200:
                    debug_print(f"Successfully downloaded tags for '{model_name}'.")
                    html_to_parse = resp.text
                    try:
                        debug_print(f"Saving HTML cache file to {cache_file}")
                        cache_file.write_text(html_to_parse, encoding="utf-8")
                    except Exception as e:
                        debug_print(f"Error saving HTML cache file for '{model_name}': {e}")
                else:
                    debug_print(f"Failed to download tags for '{model_name}'. HTTP Status: {resp.status_code}")
                    # Fallback to expired cache if available
                    if cache_file.exists():
                        debug_print(f"Falling back to expired cache file for '{model_name}'")
                        html_to_parse = cache_file.read_text(encoding="utf-8")
            except Exception as e:
                debug_print(f"Network error downloading tags for '{model_name}': {e}")
                # Fallback to expired cache if available
                if cache_file.exists():
                    try:
                        debug_print(f"Falling back to expired cache file for '{model_name}'")
                        html_to_parse = cache_file.read_text(encoding="utf-8")
                    except Exception:
                        pass

        if html_to_parse is None:
            debug_print(f"Skipping model '{model_name}' because no tag page content was retrieved.")
            continue

        try:
            tags_soup = BeautifulSoup(html_to_parse, "html.parser")
            seen_hrefs = set()
            model_tags_list = []

            for a in tags_soup.find_all("a"):
                href = a.get("href", "")
                if not href.startswith(f"/library/{model_name}:"):
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                full_tag_name = href.replace("/library/", "").strip()
                tag_suffix = full_tag_name.split(":", 1)[1] if ":" in full_tag_name else ""

                # Check if it matches target suffixes
                if tag_suffix.lower() not in TARGET_TAGS:
                    continue

                text = a.get_text()
                parts = [p.strip() for p in text.split("•") if p.strip()]

                size_or_usage = ""
                input_type = ""
                context = ""
                updated = ""

                for p in parts:
                    p_lower = p.lower()
                    if "gb" in p_lower or "mb" in p_lower or "kb" in p_lower or "usage" in p_lower:
                        size_or_usage = p
                    elif "input" in p_lower:
                        input_type = p
                    elif "context" in p_lower:
                        context = p
                    elif "ago" in p_lower or "hour" in p_lower or "day" in p_lower or "month" in p_lower or "year" in p_lower:
                        updated = p.split('\n')[0].strip()

                # Build capabilities list for this tag
                caps = []
                # Check vision (image input)
                if "image" in input_type.lower() or "vision" in text.lower():
                    caps.append("vision")
                # Add base capabilities if they match tools, thinking, audio
                for cap in ["tools", "thinking", "audio"]:
                    if cap in bm["capabilities"] or cap in text.lower():
                        caps.append(cap)
                if tag_suffix.lower() == "cloud":
                    caps.append("cloud")

                tag_dict = {
                    "model_name": full_tag_name,
                    "capabilities": caps,
                    "sizes": tag_suffix,
                    "usage": size_or_usage,
                    "context": context,
                    "input": input_type,
                    "updated": updated,
                }
                model_tags_list.append(tag_dict)

                tags_rows.append({
                    "order": order,
                    "model_name": full_tag_name,
                    "capabilities": caps,
                    "sizes": tag_suffix,
                    "usage": size_or_usage,
                    "context": context,
                    "input": input_type,
                    "updated": updated,
                    "description": bm["description"],
                })
                order += 1

            # Write model JSON info
            import json
            model_info = {
                "model_name": model_name,
                "description": bm["description"],
                "base_capabilities": bm["capabilities"],
                "tags": model_tags_list
            }
            try:
                debug_print(f"Building and saving JSON file to {json_file}")
                json_file.write_text(json.dumps(model_info, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                debug_print(f"Error saving JSON file for '{model_name}': {e}")

        except Exception as e:
            debug_print(f"Error parsing HTML and extracting tags for '{model_name}': {e}")
            # Silently skip errors for individual models
            pass

    if not tags_rows:
        print("No remote models or matching tags found.")
        return

    # 3. Filter by capabilities if specified
    normalized_filter_capabilities = {
        item.strip().lower() for item in (filter_capabilities or []) if item.strip()
    }
    if normalized_filter_capabilities:
        filtered_rows = []
        for r in tags_rows:
            capability_set = {cap.lower() for cap in r["capabilities"]}
            if capability_set.intersection(normalized_filter_capabilities):
                filtered_rows.append(r)
        tags_rows = filtered_rows

    if not tags_rows:
        print("No remote models matched the capability filters.")
        return

    # 4. Sorting
    def get_row_order(row: dict[str, Any], fallback: int) -> int:
        value = row.get("order")
        if isinstance(value, int):
            return value
        return fallback

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[object, ...]:
        fallback_index, row = item
        name_val = str(row.get("model_name", "")).lower()
        capabilities = [str(x).lower() for x in row.get("capabilities", [])]
        sizes_val = str(row.get("sizes", "")).lower()
        usage_val = str(row.get("usage", "")).lower()
        updated_val = str(row.get("updated", "")).lower()
        order_value = get_row_order(row, fallback_index)

        if sort_by == "capability":
            return (",".join(capabilities), name_val, order_value)
        if sort_by == "size":
            return (sizes_val, name_val, order_value)
        if sort_by == "usage":
            return (usage_val, name_val, order_value)
        if sort_by == "date":
            return (updated_val, name_val, order_value)
        if sort_by == "name":
            return (name_val, order_value)
        return (order_value,)

    limited_rows = tags_rows[:limit] if limit > 0 else tags_rows
    limited_rows = [
        row for _, row in sorted(enumerate(limited_rows, start=1), key=sort_key)
    ]

    local_models = get_local_models()

    printable_rows: list[list[str]] = []
    enable_color = utils.supports_color()
    for row in limited_rows:
        is_installed = is_size_installed(row["model_name"].split(":")[0], row["sizes"], local_models)

        size_val = row["sizes"]
        if is_installed:
            size_val = utils.colorize(size_val, "97;44", enable_color)

        printable_row = [
            str(row["model_name"]),
            ", ".join(row["capabilities"]),
            size_val,
            str(row["usage"]),
            str(row["updated"]),
        ]
        if with_description:
            printable_row.append(str(row["description"]))
        printable_rows.append(printable_row)

    col_count = len(columns)
    col_widths = [
        max(len(columns[i]), *(clean_len(str(row[i])) for row in printable_rows))
        for i in range(col_count)
    ]

    if with_description:
        header = "  ".join(
            ljust_ansi(str(item), col_widths[i]) for i, item in enumerate(columns[:-1])
        )
        print(header)
        print()
        for row in printable_rows:
            print(
                "  ".join(
                    ljust_ansi(str(item), col_widths[i]) for i, item in enumerate(row[:-1])
                )
            )
            print(row[-1])
            print()
    else:
        print(
            "  ".join(ljust_ansi(str(item), col_widths[i]) for i, item in enumerate(columns))
        )
        for row in printable_rows:
            print(
                "  ".join(ljust_ansi(str(item), col_widths[i]) for i, item in enumerate(row))
            )


def cmd_list_remote_models(args: Any) -> None:
    """Fetch and display models from Ollama library website."""
    from pathlib import Path
    import os
    import time
    import json

    cache_dir = Path.home() / ".ollama-cli" / "cache"

    if getattr(args, "show_cache", False):
        if getattr(args, "model", None):
            model_name = args.model
            json_file = cache_dir / f"{model_name}.json"
            debug_print(f"Reading cached JSON content for model '{model_name}' from {json_file}")
            if not json_file.exists():
                print(f"No cached JSON info found for model '{model_name}'.")
                print(f"Expected path: {json_file}")
                return
            try:
                content = json_file.read_text(encoding="utf-8")
                print(content)
            except Exception as e:
                print(f"Error reading cached JSON file: {e}")
            return

        debug_print(f"Listing files in cache directory: {cache_dir}")
        print(f"Cache folder: {cache_dir}")
        if not cache_dir.exists():
            print("Cache is empty (folder does not exist).")
            return
        files = sorted(cache_dir.glob("*.html"))
        if not files:
            print("Cache is empty.")
            return
        print(f"Cached files ({len(files)}):")
        total_size = 0
        for f in files:
            size = f.stat().st_size
            total_size += size
            mtime = f.stat().st_mtime
            age_sec = time.time() - mtime
            # Human readable age
            if age_sec < 60:
                age_str = f"{int(age_sec)}s ago"
            elif age_sec < 3600:
                age_str = f"{int(age_sec / 60)}m ago"
            elif age_sec < 86400:
                age_str = f"{int(age_sec / 3600)}h ago"
            else:
                age_str = f"{int(age_sec / 86400)}d ago"

            # format helper
            size_kb = size / 1024.0
            if size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"
            else:
                size_str = f"{size_kb / 1024.0:.1f} MB"
            print(f"  {f.name:<25} ({size_str} / {age_str})")

        total_size_kb = total_size / 1024.0
        if total_size_kb < 1024:
            total_size_str = f"{total_size_kb:.1f} KB"
        else:
            total_size_str = f"{total_size_kb / 1024.0:.1f} MB"
        print(f"Total size: {total_size_str}")
        return

    debug_print("Downloading main models list from https://ollama.com/library...")
    response = requests.get("https://ollama.com/library", timeout=20)
    response.raise_for_status()
    debug_print(f"Successfully downloaded main models page. HTTP Status: {response.status_code}")
    extract_models(
        response.text,
        limit=args.limit,
        with_description=args.with_description,
        filter_capabilities=args.filter_capabilities,
        sort_by=args.sort_by,
        force=args.force,
    )
