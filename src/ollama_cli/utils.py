#!/usr/bin/env python3
import csv
import os
import sys
from pathlib import Path
from typing import Any


# ============================================================
#  Size and format helpers
# ============================================================
def size_bytes(path: Path) -> int:
    """Get file size in bytes."""
    try:
        return path.stat().st_size
    except Exception:
        return 0


def format_size(b: int, unit: str) -> str:
    """Format bytes to human-readable size."""
    if unit == "gb":
        return f"{b / (1024**3):.2f} GB"
    return f"{b / (1024**2):.2f} MB"


# ============================================================
#  Color and output helpers
# ============================================================
def supports_color() -> bool:
    """Check if terminal supports color output."""
    return os.isatty(1)


def colorize(text: str, color: str, enable: bool) -> str:
    """Apply ANSI color codes to text if enabled."""
    return f"\033[{color}m{text}\033[0m" if enable else text


# ============================================================
#  Table / CSV output
# ============================================================
def print_table(rows: list[dict], columns: list[str], enable_color: bool) -> None:
    """Print a formatted table with optional color support."""
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
    """Write rows to CSV file or stdout."""
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
    """Display a simple progress bar."""
    if total <= 0:
        return
    width = 30
    ratio = current / total
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{prefix}[{bar}] {current}/{total}", end="", flush=True)


# ============================================================
#  Parsing helpers
# ============================================================
def parse_size_to_bytes(size_str: str) -> int:
    """Parse human-readable size string to bytes."""
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
    """Parse relative time string (e.g., '2 days ago') to seconds."""
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
