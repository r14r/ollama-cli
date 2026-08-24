# ollama-cli

A Go CLI + Docker Compose stack for running a self-hosted [Ollama](https://ollama.com) server, with a
convenience wrapper around it. `ollama-cli` is not the Ollama binary itself — nearly every subcommand
shells out to `docker compose exec ollama ollama ...` inside a running container, and any subcommand it
doesn't recognize is proxied straight through to the real `ollama` CLI in the container. So `ollama-cli
show <model>`, `ollama-cli cp ...`, etc. all just work without being reimplemented.

The stack (`docker/docker-compose.yaml`) runs:

| Service      | Purpose                                                              |
|--------------|-----------------------------------------------------------------------|
| `ollama`     | The Ollama server itself                                              |
| `gateway`    | Python/FastAPI proxy in front of Ollama                               |
| `frontend`   | Streamlit admin UI                                                    |
| `openwebui`  | [Open WebUI](https://github.com/open-webui/open-webui) chat frontend  |
| `ollama-init`| One-shot job: pulls a model list into Ollama on `up`, then exits      |
| `mongodb`    | Database backing LibreChat                                            |
| `librechat`  | [LibreChat](https://github.com/danny-avila/LibreChat) chat frontend   |

Plus an optional monitoring stack (`docker-compose.monitoring.yaml`): Prometheus, Grafana, cAdvisor.

---

## QUICKSTART

Everything, start to first chat, in order:

```bash
# 1. Clone and enter the repo
git clone <this-repo-url> ollama-cli
cd ollama-cli

# 2. Build and install the ollama-cli binary
just install
# -> builds go/ and copies the binary to /Users/Shared/CLOUD/DeveloperTools/bin
#    make sure that directory is on your $PATH

# 3. Configure the Docker stack
# edit docker/.env: set ADMIN_USER / ADMIN_PASSWORD and, for LibreChat, rotate
# LIBRECHAT_JWT_SECRET / LIBRECHAT_JWT_REFRESH_SECRET / LIBRECHAT_CREDS_KEY / LIBRECHAT_CREDS_IV
$EDITOR docker/.env

# 4. Point ollama-cli at the compose stack (skip if running from this repo's dev path)
export OLLAMA_COMPOSE_DIR="$(pwd)/docker"

# 5. Start everything (builds images on first run)
ollama-cli up

# 6. Pull the default model set into the running container
ollama-cli install-defaults

# 7. Check status
ollama-cli status

# 8. Talk to a model
ollama-cli launch chat
```

Open WebUI: `http://localhost:${OPENWEBUI_PORT_PUBLIC}` (default `11010`)
LibreChat: `http://localhost:${LIBRECHAT_PORT_PUBLIC}` (default `11020`)
Admin frontend: `http://localhost:${OLLAMA_ADMIN_PORT_PUBLIC}` (default `11000`)

---

## INSTALL

### Requirements

- Go 1.21+ (to build the CLI)
- Docker + Docker Compose v2 (`docker compose`, not `docker-compose`)
- [`just`](https://github.com/casey/just) (runs the recipes below; optional, you can call the underlying
  commands directly)

### Build & install the CLI

```bash
just build     # go build -> dist/go/ollama-cli
just install   # build + copy to /Users/Shared/CLOUD/DeveloperTools/bin, chmod +x
```

Or without `just`:

```bash
cd go && go build -ldflags="-s -w" -o ../dist/go/ollama-cli .
```

Verify:

```bash
ollama-cli --version
# ollama version: <container ollama version>
# ollama-cli version: <contents of go/cmd/VERSION>
```

### Configure the Docker stack

The stack lives under `docker/`. Copy/edit `docker/.env` before first boot — at minimum:

- `ADMIN_USER` / `ADMIN_PASSWORD` — admin creds for the frontend/gateway
- `LIBRECHAT_JWT_SECRET`, `LIBRECHAT_JWT_REFRESH_SECRET`, `LIBRECHAT_CREDS_KEY` (32-byte hex),
  `LIBRECHAT_CREDS_IV` (16-byte hex) — regenerate for anything beyond local dev:
  ```bash
  openssl rand -hex 32   # JWT_SECRET, JWT_REFRESH_SECRET, CREDS_KEY
  openssl rand -hex 16   # CREDS_IV
  ```
- `docker/models.yaml` — models the `ollama-init` service preloads on `up` (top-level `models:` list).
  Override the path with `OLLAMA_MODELS_FILE`.

### Point the CLI at the stack

`ollama-cli` resolves the compose file in this order:

1. `OLLAMA_COMPOSE_DIR` env var
2. `~/.ollama-cli/docker/` (if it contains `docker-compose.yaml`)
3. a hardcoded dev path
4. current working directory

For a normal install, either export `OLLAMA_COMPOSE_DIR=/path/to/ollama-cli/docker`, or run
`ollama-cli setup` to scaffold `~/.ollama-cli/{docker/,setup.yml}` and copy `docker/` there.

### First boot

```bash
ollama-cli up               # docker compose up -d
ollama-cli install-defaults # pull the default model set
ollama-cli status           # container + model status
```

---

## Usage

```bash
ollama-cli <command> [args]
```

### Stack lifecycle

| Command                     | What it does                                                     |
|------------------------------|--------------------------------------------------------------------|
| `up`                         | Start the stack (`docker compose up -d`)                          |
| `down`                       | Stop the stack                                                     |
| `build`                      | Pull the base Ollama image and rebuild the `ollama` service        |
| `build --with-models <file>` | `build`, then pull every model listed in `<file>` into the container |
| `rebuild`                    | Pull latest images, clean-build all services (`--no-cache`), start |
| `status`                     | Show container + model status                                      |
| `shell`                      | Open a shell inside the Ollama container                           |
| `version` / `--version`      | Show ollama (container) and ollama-cli versions                    |

### Models

| Command                          | What it does                                              |
|-----------------------------------|-------------------------------------------------------------|
| `install-defaults`                 | Pull the default model list (`setup.yml` or built-in fallback) |
| `install-models --group <name>`    | Pull a named model group from `setup.yml` (`<group>_models`) |
| `update-models`                    | Pull the latest version of every currently installed model |
| `update-models --with-models <file>` | Pull the latest version of every model listed in `<file>` instead |
| `list` / `ls`                      | List local models in the container                         |
| `list-remote`                      | Browse models available on the Ollama library website      |
| `models`                           | List models with blob counts and total disk usage          |
| `blobs`                            | Inspect blobs/manifests, find orphaned blob files           |

### Launch profiles

| Command             | What it does                                        |
|-----------------------|--------------------------------------------------------|
| `profiles`             | List available launch profiles and their models        |
| `launch <profile>`     | Run `ollama run <model>` for a named profile            |

Built-in profiles: `claude`, `opencode`, `chat`, `fast`, `reason`, `embed`, `hermes`. Override any
profile's model with `OLLAMA_LAUNCH_<PROFILE>_MODEL`.

### Setup

| Command              | What it does                                                    |
|------------------------|--------------------------------------------------------------------|
| `setup`                | Scaffold `~/.ollama-cli/{docker/,setup.yml}`                        |
| `setup --edit`         | Same, then open `setup.yml` in `$EDITOR`                            |

### Anything else

Any subcommand `ollama-cli` doesn't recognize is proxied straight to `ollama` inside the container, e.g.:

```bash
ollama-cli show llama3.2:1b
ollama-cli cp llama3.2:1b my-copy
ollama-cli rm my-copy
```

---

## Configuration reference

### `ollama-cli` env vars

| Var                          | Default              | Purpose                                            |
|-------------------------------|-----------------------|------------------------------------------------------|
| `OLLAMA_COMPOSE_DIR`           | (auto-resolved)       | Directory containing `docker-compose.yaml`           |
| `OLLAMA_COMPOSE_SERVICE`       | `ollama`               | Compose service to exec into                          |
| `OLLAMA_PROJECT_NAME`          | `ai-tools-ollama`      | Compose project name                                  |
| `OLLAMA_DEFAULT_MODELS`        | (built-in list)        | Space-separated model list, overrides `setup.yml`     |
| `OLLAMA_LAUNCH_<PROFILE>_MODEL`| per-profile default    | Override the model for a `launch`/`profiles` profile  |
| `OLLAMA_DEBUG`                 | off                    | Verbose debug output                                   |
| `NO_COLOR`                     | off                    | Disable ANSI colorizing in table output               |

### Docker stack env vars (`docker/.env`)

See `docker/.env` for the full list (ports, image tags, admin creds, LibreChat secrets,
`OLLAMA_MODELS_FILE`). Every `*_PORT_PUBLIC` var controls the host-side port for that service.

---

## Project layout

```
go/                   Go CLI source (the only active codebase; entry point go/main.go)
  cmd/                 Cobra subcommands
  internal/compose/    docker compose invocation, service targeting, TTY handling
  internal/config/     setup.yml / model-group / models-file parsing
  internal/models/     `ollama list` helpers
  internal/remote/     ollama.com model library scraper + cache
  internal/blobscan/   blob/manifest inspection for `blobs`
  internal/utils/      output formatting helpers
docker/               Docker Compose stack: services, .env, models.yaml, monitoring
justfile              Build/install recipes for the Go CLI
docker/justfile        Compose lifecycle recipes (up/down/build/rebuild/logs/...)
```

There is no Go test suite currently (`go test ./...` finds nothing).
