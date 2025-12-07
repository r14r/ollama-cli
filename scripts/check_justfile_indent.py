#!/usr/bin/env python3
import sys
from pathlib import Path

JUSTFILE = Path("justfile")


def main() -> int:
    if not JUSTFILE.exists():
        # No justfile? Nothing to check.
        return 0

    bad_lines = []

    for i, raw in enumerate(JUSTFILE.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.rstrip("\n")

        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("#"):
            continue

        # Forbid any lines starting with a space
        if line.startswith(" "):
            bad_lines.append((i, line))

    if not bad_lines:
        return 0

    print("ERROR: justfile contains lines with leading spaces (Just requires tabs for recipe bodies).", file=sys.stderr)
    print("Offending lines:", file=sys.stderr)
    for lineno, content in bad_lines:
        print(f"  line {lineno}: {content!r}", file=sys.stderr)

    print("\nFix: Replace leading spaces with tabs on recipe lines.", file=sys.stderr)
    print("The auto-fix hook scripts/fix_justfile_indent.py should usually fix this automatically.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
