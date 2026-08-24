# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This repo just went through a full rewrite: Python (`src/ollama_cli/`, PyInstaller/shiv packaging, Homebrew formula) → Go (`go/`). The Python tree, `pyproject.toml`, `ollama-cli.spec`, `pyoxidizer.bzl`, and `homebrew/` are deleted in the working tree but not yet purged from git history/justfile references. **The Go implementation under `go/` is the only active codebase.** Don't resurrect or "fix" the Python files — they're being removed intentionally.

## What this tool is

`ollama-cli` is a Docker Compose wrapper + convenience CLI around a self-hosted Ollama stack (`docker/docker-compose.yaml`: `ollama`, `gateway`, `frontend` services). It is not the Ollama binary itself — nearly every subcommand shells out to `docker compose exec <service> ollama ...` in a running container.

## Build & run

```bash
just build          # go build -> dist/go/ollama-cli
just install          # build + copy to /Users/Shared/CLOUD/DeveloperTools/bin
cd go && go build -o ../dist/go/ollama-cli .   # direct build
cd go && go run . <subcommand>                  # run from source
cd go && go vet ./...
```

There is no Go test suite currently (`go test ./...` finds nothing).

## Architecture

Entry point `go/main.go` does one job before handing off to Cobra: it rewrites legacy flag-style invocations (`--up`, `--status`, `--launch`, etc.) into positional subcommands for backward compat with the old Python CLI's argument style, then calls `cmd.Execute()`.

`go/cmd/root.go` wires all subcommands onto `rootCmd`. Any command not registered with Cobra is **not** an error — `handleUnknownCommand`/`Execute()` proxies it straight through to `docker compose exec <service> ollama <args...>`. This is how raw `ollama` subcommands (`ollama-cli show ...`, `ollama-cli cp ...`) work without being reimplemented in Go.

Package responsibilities under `go/internal/`:
- **`compose`** — all `docker compose` invocation logic: resolving which `docker-compose.yaml` to use (env var → `~/.ollama-cli/docker/` → hardcoded dev path → cwd), building/running compose commands, TTY detection (adds `-T` to `exec` when not a TTY, e.g. piped/non-interactive use), ensuring the service container is up before exec'ing into it. Every command that talks to the container goes through `compose.ComposeExec`/`ComposeExecCapture`.
- **`config`** — reads `~/.ollama-cli/setup.yml` for default model lists and named model groups (`<group>_models` keys), falls back to `OLLAMA_DEFAULT_MODELS` env var, then a hardcoded default list.
- **`models`** — thin layer over `ollama list` output (via `compose.ComposeExecCapture`) to check if a model is pulled and list installed models.
- **`remote`** — scrapes ollama.com's model library/tags pages with goquery, with a 24h on-disk HTML cache under `~/.ollama-cli/cache/` (falls back to expired cache on fetch failure). Backs `list-remote`.
- **`blobscan`** — walks Ollama's manifest directory structure to map blob SHA256 digests back to model names, and lists blob files under the blobs dir. Backs `blobs` (orphaned blob detection/cleanup).
- **`utils`** — output formatting helpers (byte-size formatting, ANSI colorizing gated by `NO_COLOR`, relative-time parsing, table printing).

### Key env vars

- `OLLAMA_COMPOSE_DIR` — override compose file location
- `OLLAMA_COMPOSE_SERVICE` (default `ollama`) / `OLLAMA_PROJECT_NAME` (default `ai-tools-ollama`) — compose project/service targeting
- `OLLAMA_DEFAULT_MODELS` — override default model pull list
- `OLLAMA_LAUNCH_<PROFILE>_MODEL` — override model for a `launch`/`profiles` profile (claude, opencode, chat, fast, reason, embed, hermes)
- `OLLAMA_DEBUG` — enables debug output in `root.go`
- `NO_COLOR` — disables ANSI colorizing in table output

### Command → package map

`up`/`down`/`build`/`status`/`shell`/`version` are thin compose wrappers in `go/cmd/*.go`. `launch`/`profiles` resolve a profile name to a model and run it. `install-defaults`/`install-models`/`update-models` pull model sets via `config` + `models`. `list-remote` drives `remote`. `blobs` drives `blobscan`. `setup` scaffolds `~/.ollama-cli/{docker/,setup.yml}`.

## `docker/` directory

Separate deployable stack (compose files, per-service Dockerfiles, a Streamlit `frontend/`, a `gateway/` proxy, Prometheus/Grafana monitoring under `infra/`). This is the actual Ollama service infrastructure the Go CLI manages remotely — changes here affect the running containers, not the CLI binary itself.
