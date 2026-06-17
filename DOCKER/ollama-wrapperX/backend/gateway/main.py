import os

import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prometheus_fastapi_instrumentator import Instrumentator

from extended.db import init_db

from extended.chat       import router as router_chat
from extended.models     import router as router_models
from extended.monitoring import router as router_monitoring
from extended.prompts    import router as router_prompts
from extended.templates  import router as router_templates

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

app = FastAPI(title="Ollama Extended Gateway")

Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
def on_startup():
    init_db()

#
#
#
app.include_router(router_chat,         prefix="/extended/chat",        tags=["chat"])
app.include_router(router_models,       prefix="/extended/models",      tags=["models"])
app.include_router(router_monitoring,   prefix="/extended/monitoring",  tags=["monitoring"])
app.include_router(router_prompts,      prefix="/extended/prompts",     tags=["prompts"])
app.include_router(router_templates,    prefix="/extended/templates",   tags=["templates"])


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_ollama(full_path: str, request: Request):
    target_url = f"{OLLAMA_URL}/{full_path}"

    method = request.method
    headers = dict(request.headers)
    body = await request.body()

    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.request(
            method=method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params,
        )

    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception:
            return JSONResponse(status_code=resp.status_code, content={"raw": resp.text})
    return JSONResponse(status_code=resp.status_code, content={"raw": resp.text})
