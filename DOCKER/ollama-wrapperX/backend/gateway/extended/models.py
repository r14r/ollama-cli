import os
import time
import httpx

from fastapi import APIRouter, HTTPException

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

router = APIRouter()


@router.get("/")
async def extended_models():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            version = None
            try:
                v_resp = await client.get(f"{OLLAMA_URL}/api/version")
                if v_resp.status_code == 200:
                    version = v_resp.json()
            except Exception:
                version = None

            tags_resp = await client.get(f"{OLLAMA_URL}/api/tags")
            ps_resp = await client.get(f"{OLLAMA_URL}/api/ps")

        if tags_resp.status_code != 200:
            raise HTTPException(status_code=tags_resp.status_code, detail=tags_resp.text)
        if ps_resp.status_code != 200:
            raise HTTPException(status_code=ps_resp.status_code, detail=ps_resp.text)

        models = tags_resp.json().get("models", [])
        running = ps_resp.json().get("models", [])

        return {
            "service": "ollama-extended-gateway",
            "ollama_url": OLLAMA_URL,
            "version": version,
            "installed_models": models,
            "running_models": running,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(f"{OLLAMA_URL}/api/tags")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    models = data.get("models", [])
    return {
        "object": "list",
        "data": [
            {
                "id": m.get("name"),
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama",
                "metadata": m,
            }
            for m in models
        ],
    }


@router.get("/running")
async def extended_models_running():
    return "TO BE IMPLEMENTED"
