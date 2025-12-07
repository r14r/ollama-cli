#!/usr/bin/env python3
import sys
from pathlib import Path
import re

JUSTFILE = Path("justfile")


def fix_justfile() -> bool:
    """
    Auto-fix leading spaces in justfile:

    - For any non-empty, non-comment line that starts with spaces,
      replace the leading spaces with a single TAB.
    - Returns True if file was modified, False otherwise.
    """
    if not JUSTFILE.exists():
        return False

    original = JUSTFILE.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    new_lines = []

    for line in original:
        # Keep line endings intact
        text = line.rstrip("\n\r")
        newline = line[len(text):]  # usually "\n"

        stripped = text.lstrip()
        # Ignore blank lines or pure comment lines
        if stripped == "" or stripped.startswith("#"):
            new_lines.append(text + newline)
            continue

        if text.startswith(" "):
            # Replace ALL leading spaces with a single tab.
            # Just requires tabs for recipe lines; spaces never work there.
            fixed = re.sub(r"^ +", "\t", text)
            if fixed != text:
                changed = True
                text = fixed

        new_lines.append(text + newline)

    if changed:
        JUSTFILE.write_text("".join(new_lines), encoding="utf-8")

    return changed


def main() -> int:
    try:
        changed = fix_justfile()
    except Exception as e:
        print(f"fix_justfile_indent.py: error while fixing justfile: {e}", file=sys.stderr)
        return 1

    if changed:
        print("fix_justfile_indent.py: fixed leading spaces in justfile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
