set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

APP := "ollama-cli"
export VIRTUAL_ENV := ".venv/python"
VENV := ".venv"
BIN := VENV + "/python/bin"
CLI := BIN + "/" + APP
DEPLOY_DIR := "/Users/Shared/CLOUD/DeveloperTools/bin"
DEPLOY_TARGET := DEPLOY_DIR + "/" + APP

# ------------------------------------------------------------
# CONFIG – EDIT THESE
# ------------------------------------------------------------

GITHUB_USER := "r14r"
TOOL_REPO   := "ollama-cli"
TOOL_SCRIPT := "src/ollama_cli/cli.py"
FORMULA_FILE := "homebrew-ollama-cli/Formula/ollama-cli.rb"

# Show available commands
help:
    @just --list

# Create virtualenv using venv setup python
setup-env:
    venv setup python
    direnv-allow

# Install editable package into current venv
install-env:
    uv pip install -e .

# Run CLI help
cli-help:
    {{BIN}}/{{APP}} --help

# Run the CLI from source without installing
run *args:
    {{BIN}}/python -m ollama_cli {{args}}

# Run a quick syntax check
check:
    {{BIN}}/python -m compileall src

# Show package version information
version:
    {{BIN}}/{{APP}} --version

# Ask the user for the next version increment and update project files
ask-version-increment:
    #!/usr/bin/env bash
    set -euo pipefail
    CURRENT_VERSION=$(grep -E '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/')
    NEW_VERSION=$(ask-version-increment "$CURRENT_VERSION")
    if [ "$NEW_VERSION" != "$CURRENT_VERSION" ]; then
        echo "Updating version from $CURRENT_VERSION to $NEW_VERSION..."
        if [ "$(uname)" = "Darwin" ]; then SED_INPLACE=(-i ''); else SED_INPLACE=(-i); fi
        sed "${SED_INPLACE[@]}" "s/^version = \".*\"/version = \"${NEW_VERSION}\"/" pyproject.toml
        sed "${SED_INPLACE[@]}" "s/version=f\"ollama-cli version [0-9.]* /version=f\"ollama-cli version ${NEW_VERSION} /" src/ollama_cli/cli.py
    else
        echo "Version remains at $CURRENT_VERSION."
    fi

# Build standalone binary using PyInstaller
build-pyinstaller: ask-version-increment
    rm -rf build dist/pyinstaller dist/*.spec
    mkdir -p dist/pyinstaller
    {{BIN}}/pyinstaller --onefile --name {{APP}} --distpath dist/pyinstaller src/ollama_cli/__main__.py
    echo "pyinstaller" > dist/pyinstaller/build_source.txt

# Clean generated files
clean:
	rm -rf build dist *.egg-info src/*.egg-info src/ollama_cli.egg-info .pytest_cache
	find . -name _pycache__ -delete

# ------------------------------------------------------------
config:
	echo "GITHUB_USER  = {{GITHUB_USER}}"
	echo "TOOL_REPO    = {{TOOL_REPO}}"
	echo "TOOL_SCRIPT  = {{TOOL_SCRIPT}}"
	echo "FORMULA_FILE = {{FORMULA_FILE}}"

sha-remote:
	set -euo pipefail
	TOOL_URL="https://raw.githubusercontent.com/{{GITHUB_USER}}/{{TOOL_REPO}}/main/{{TOOL_SCRIPT}}"
	echo "Fetching: $TOOL_URL"
	curl -L "$TOOL_URL" | shasum -a 256

sha-local:
	set -euo pipefail
	if [ ! -f "src/ollama_cli/cli.py" ]; then echo "Local file 'src/ollama_cli/cli.py' not found in this repo." >&2; exit 1; fi
	echo "Calculating SHA for local src/ollama_cli/cli.py"
	shasum -a 256 "src/ollama_cli/cli.py"

update-formula:
	set -euo pipefail
	TOOL_URL="https://raw.githubusercontent.com/{{GITHUB_USER}}/{{TOOL_REPO}}/main/{{TOOL_SCRIPT}}"
	echo "Updating sha256 in {{FORMULA_FILE}} from remote: $TOOL_URL"
	SHA=$(curl -L "$TOOL_URL" | shasum -a 256 | awk '{print $$1}')
	echo "New SHA: $SHA"
	if [ ! -f "{{FORMULA_FILE}}" ]; then echo "Formula file '{{FORMULA_FILE}}' not found." >&2; exit 1; fi
	# macOS vs Linux sed -i
	if [ "$(uname)" = "Darwin" ]; then SED_INPLACE=(-i ''); else SED_INPLACE=(-i); fi
	sed "${SED_INPLACE[@]}" "s/^  sha256 \".*\"/  sha256 \"${SHA}\"/" "{{FORMULA_FILE}}"
	echo "Updated {{FORMULA_FILE}}:"
	grep "sha256" "{{FORMULA_FILE}}"

commit-push msg="Update ollama-cli formula":
	set -euo pipefail
	git add "{{FORMULA_FILE}}"
	if git diff --cached --quiet; then echo "Nothing to commit."; exit 0; fi
	git commit -m "{{msg}}"
	git push
	echo "Pushed formula changes."

# Build standalone binary using Go
build:
	mkdir -p dist/go
	cd go && go build -ldflags="-s -w" -o ../dist/go/ollama-cli .

# Install Go binary to DeveloperTools/bin
install: build
	mkdir -p {{DEPLOY_DIR}}
	cp dist/go/ollama-cli {{DEPLOY_TARGET}}
	chmod +x {{DEPLOY_TARGET}}
	echo "Deployed Go version to {{DEPLOY_TARGET}}"
	@{{DEPLOY_TARGET}} --version

release:
	set -euo pipefail
	just update-formula
	just commit-push msg="Update ollama-cli sha"

