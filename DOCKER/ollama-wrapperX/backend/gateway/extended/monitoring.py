import os
import httpx

from fastapi import APIRouter, HTTPException

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

router = APIRouter()


@router.get("/health")
async def health():
    try:
        version = {}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                v_resp = await client.get(f"{OLLAMA_URL}/api/version")
                if v_resp.status_code == 200:
                    version = v_resp.json()
            except Exception:
                pass

        return {
            "state": "OK",
            "version": version['version'],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def extended_status():
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
