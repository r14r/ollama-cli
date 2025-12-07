set shell := ["bash", "-cu"]

# ------------------------------------------------------------
# CONFIG – EDIT THESE
# ------------------------------------------------------------

GITHUB_USER := "r14r"
TOOL_REPO   := "ollama-cli"
TOOL_SCRIPT := "ollama-cli.py"
FORMULA_FILE := "Formula/ollama-cli.rb"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

config:
	echo "GITHUB_USER  = $GITHUB_USER"
	echo "TOOL_REPO    = $TOOL_REPO"
	echo "TOOL_SCRIPT  = $TOOL_SCRIPT"
	echo "FORMULA_FILE = $FORMULA_FILE"

sha-remote:
	set -euo pipefail
	TOOL_URL="https://raw.githubusercontent.com/${GITHUB_USER}/${TOOL_REPO}/main/${TOOL_SCRIPT}"
	echo "Fetching: $TOOL_URL"
	curl -L "$TOOL_URL" | shasum -a 256

sha-local:
	set -euo pipefail
	if [ ! -f "$TOOL_SCRIPT" ]; then echo "Local file '$TOOL_SCRIPT' not found in this repo." >&2; exit 1; fi
	echo "Calculating SHA for local $TOOL_SCRIPT"
	shasum -a 256 "$TOOL_SCRIPT"

# ------------------------------------------------------------
# Update Formula
# ------------------------------------------------------------

update-formula:
	set -euo pipefail
	TOOL_URL="https://raw.githubusercontent.com/${GITHUB_USER}/${TOOL_REPO}/main/${TOOL_SCRIPT}"
	echo "Updating sha256 in $FORMULA_FILE from remote: $TOOL_URL"
	SHA=$(curl -L "$TOOL_URL" | shasum -a 256 | awk '{print $$1}')
	echo "New SHA: $SHA"
	if [ ! -f "$FORMULA_FILE" ]; then echo "Formula file '$FORMULA_FILE' not found." >&2; exit 1; fi
	# macOS vs Linux sed -i
	if [ "$(uname)" = "Darwin" ]; then SED_INPLACE=(-i ''); else SED_INPLACE=(-i); fi
	sed "${SED_INPLACE[@]}" "s/^  sha256 \".*\"/  sha256 \"${SHA}\"/" "$FORMULA_FILE"
	echo "Updated $FORMULA_FILE:"
	grep "sha256" "$FORMULA_FILE"

# ------------------------------------------------------------
# Deploy
# ------------------------------------------------------------

deploy msg="Update ollama-cli formula":
	set -euo pipefail
	git add "$FORMULA_FILE"
	if git diff --cached --quiet; then echo "Nothing to commit."; exit 0; fi
	git commit -m "{{msg}}"
	git push
	echo "Pushed formula changes."

# ------------------------------------------------------------
# Release = Update SHA + push
# ------------------------------------------------------------

release:
	set -euo pipefail
	just update-formula
	just deploy msg="Update ollama-cli sha"
