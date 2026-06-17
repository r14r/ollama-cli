#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") <version>" >&2
    echo "  version: current version in semver format (e.g. 1.2.3)" >&2
    exit 1
}

[[ $# -eq 1 ]] || usage

CURRENT="$1"

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
MINOR=${MINOR:-0}
PATCH=${PATCH:-0}

LABELS=( "major"  "minor"  "bugfix" "current" )
VERSIONS=(
    "$((MAJOR + 1)).0.0"
    "$MAJOR.$((MINOR + 1)).0"
    "$MAJOR.$MINOR.$((PATCH + 1))"
    "$MAJOR.$MINOR.$PATCH"
)

# ── interactive menu ──────────────────────────────────────────────────────────
# Default: index 2 (bugfix). Returns chosen index in SELECTED_IDX.
select_menu() {
    local selected=2          # default: bugfix
    local count=${#LABELS[@]} # 4
    local total_lines=$(( count + 2 ))  # header (2 lines) + options (count lines)
    local key esc

    # Pre-cache tput escape sequences to variables to avoid process overhead in the loop
    local civis cnorm clear_line cuu
    civis=$(tput civis 2>/dev/null || true)
    cnorm=$(tput cnorm 2>/dev/null || true)
    clear_line=$(tput el 2>/dev/null || true)
    cuu=$(tput cuu "$total_lines" 2>/dev/null || true)

    # Render header + all option rows.
    render() {
        # Line 1: Current version with white text (\033[37m) and blue background (\033[44m)
        # Line 2: Static prompt "Which part to increment?:" without showing selection preview
        printf "\r%sCurrent version is \033[37;44m %s \033[0m. \n\r%sWhich part to increment?:\n" \
            "$clear_line" "$CURRENT" \
            "$clear_line" >&2

        for i in "${!LABELS[@]}"; do
            if [[ $i -eq $selected ]]; then
                printf "\r%s\033[7m   %d.  %-7s → %s \033[0m\n" "$clear_line" $((i+1)) "${LABELS[$i]}" "${VERSIONS[$i]}" >&2
            else
                printf "\r%s   %d.  %-7s → %s\n" "$clear_line" $((i+1)) "${LABELS[$i]}" "${VERSIONS[$i]}" >&2
            fi
        done
    }

    printf "%s" "$civis" >&2
    render

    while true; do
        IFS= read -rsn1 key || break

        # Number key: move highlight to that row (adjusted to count)
        if [[ "$key" =~ ^[1-$count]$ ]]; then
            local n=$(( key - 1 ))
            selected=$n
            printf "%s" "$cuu" >&2
            render
            continue
        fi

        # Arrow keys / Escape key
        if [[ "$key" == $'\x1b' ]]; then
            IFS= read -rsn2 -t 0.1 esc || true
            if [[ -z "$esc" ]]; then
                # Escape key pressed (timed out reading trailing escape code characters)
                printf "%s" "$cnorm" >&2
                printf "\n" >&2
                echo "$CURRENT"
                exit 0
            fi
            case "$esc" in
                '[A')  # up
                    (( selected-- )) || true
                    (( selected < 0 )) && selected=$(( count - 1 ))
                    ;;
                '[B')  # down
                    (( selected++ )) || true
                    (( selected >= count )) && selected=0
                    ;;
            esac
            printf "%s" "$cuu" >&2
            render
            continue
        fi

        # Enter / return → confirm
        if [[ "$key" == '' || "$key" == $'\n' || "$key" == $'\r' ]]; then
            break
        fi
    done

    printf "%s" "$cnorm" >&2
    printf "\n" >&2
    SELECTED_IDX=$selected
}

# ─────────────────────────────────────────────────────────────────────────────

select_menu

case $SELECTED_IDX in
    0) NEW_VERSION="${VERSIONS[0]}" ;;
    1) NEW_VERSION="${VERSIONS[1]}" ;;
    2) NEW_VERSION="${VERSIONS[2]}" ;;
    3) NEW_VERSION="${VERSIONS[3]}" ;;
esac

echo "$NEW_VERSION"
