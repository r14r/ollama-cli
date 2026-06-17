# v3 Unified stack

This directory merges the v1 + v2 docker-compose environments and introduces:

- A FastAPI gateway that now also proxies every Ollama model lifecycle endpoint (list, pull, create, show, stop, copy, push, run) on top of the existing prompt logging/metrics surface.
- A Streamlit-based `frontend` UI that talks to the gateway for models, templates, monitoring, and chat so the admin API service itself is no longer needed.
- An OpenWebUI frontend (exposed on `OPENWEBUI_PORT_PUBLIC`) so you can access a polished web chat experience directly against the same Ollama/Gateway backend; it reuses the Ollama model cache and the `ghcr.io/open-webui/open-webui:ollama` image from the recommended Docker command.
- Full Prometheus + Grafana monitoring plus client SDK helpers and LangChain/LangGraph examples (Prometheus/Grafana are customized with `ADMIN_USER`/`ADMIN_PASSWORD` from `.env`).
- A lightweight cAdvisor container exposes host-level metrics on `http://localhost:8080` so Prometheus/Grafana can scrape the host Docker daemon without extra configuration.

## Structure

```
backend/
  gateway/       # FastAPI gateway + logging + metrics that now wraps Ollama for models & prompts
frontend/
  frontend/  # Streamlit admin dashboard talking to the gateway for both admin + chat workflows
infra/
  services/        # Docker Compose that wires Ollama, gateway, admin API, UI, Prometheus, and Grafana
  monitoring/    # Quick reference for monitoring stack
  grafana/       # Provisioned Grafana datasource
  prometheus/    # Prometheus scrape configuration
  shared/        # SDK helpers + LangChain/LangGraph integration samples
clients/
  langchain/     # LangChain demo hitting the gateway
  postman/       # Postman collection for exercising the extended gateway surface
```

## Quick start (from `v3` root)

```bash
cd docker
docker compose up --build
```

- Ollama API stays on `http://localhost:11434`.
- Gateway listens on `http://localhost:11100` and exposes `/chat`, `/v1/chat/completions`, `/prompts`, `/metrics`, etc.
- Streamlit UI is `http://localhost:11000`.
- OpenWebUI is available at `http://localhost:11010`.
- cAdvisor exposes Docker metrics on `http://localhost:8080`.
- Prometheus + Grafana are available at `http://localhost:9090` and `http://localhost:3000`.

## Notes

- Use `infra/shared/sdk/python/gateway_sdk.py` to programmatically interact with the gateway from other clients.
- Example LangChain/LangGraph integration is under `infra/shared/lang/`.
- `v3/.env` pins all endpoints to the local Ollama API, points the UI and gateway at those services, sets Grafana/Prometheus credentials via `ADMIN_USER`/`ADMIN_PASSWORD`, and keeps `ALLOW_OPENAI=0` so every AI call stays on-prem.
- The same `.env` file also lists every host-facing port (`OLLAMA_PORT_PUBLIC`, `GATEWAY_PORT_PUBLIC`, etc.) so you can remap services without editing `docker-compose.yml`.
- Use `clients/langchain/langchain_example.py` or `clients/postman/ollama-extended-gateway.postman_collection.json` to exercise the gateway from other tooling.

## Tasks via `just`

`v3/justfile` wraps the compose stack so you can start/stop, watch logs, and rebuild without typing the full compose path; every recipe already loads `v3/.env`.

```
just up            # build + start the stack
just down          # stop everything
just logs          # tail all logs
just gateway-logs   # tail only the gateway
just frontend-logs  # tail only the Streamlit UI
just build         # rebuild all service images
just compose-ps    # show container status
just gateway-shell  # open a shell inside the gateway service
just prometheus    # tail Prometheus logs
```
# ollama-wrapper
