import os
import httpx
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .db import get_connection

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

router = APIRouter()


class PromptIn(BaseModel):
    name: str = Field(..., description="Display name of the prompt")
    description: Optional[str] = None
    prompt: str = Field(..., description="Prompt text")


class PromptOut(PromptIn):
    id: int
    created_at: str
    updated_at: str


class PromptRunRequest(BaseModel):
    model: str = "llama3"
    temperature: float = 0.7


class PromptRunResponse(BaseModel):
    prompt_id: int
    model: str
    response: str


def row_to_prompt(row) -> PromptOut:
    return PromptOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        prompt=row["prompt"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/", response_model=List[PromptOut])
def list_prompts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, description, prompt, created_at, updated_at
        FROM prompts
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [row_to_prompt(r) for r in rows]

@router.get("/recent")
def recent(limit: int = 50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT timestamp, model, prompt, response, duration
        FROM prompt_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "timestamp": r["timestamp"],
            "model": r["model"],
            "prompt": r["prompt"],
            "response": r["response"],
            "duration": r["duration"],
        }
        for r in rows
    ]


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, description, prompt, created_at, updated_at
        FROM prompts
        WHERE id = ?
        """,
        (prompt_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return row_to_prompt(row)


@router.post("/", response_model=PromptOut)
def save_prompt(prompt: PromptIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO prompts (name, description, prompt)
        VALUES (?, ?, ?)
        """,
        (prompt.name, prompt.description, prompt.prompt),
    )
    pid = cur.lastrowid
    conn.commit()

    cur.execute(
        """
        SELECT id, name, description, prompt, created_at, updated_at
        FROM prompts
        WHERE id = ?
        """,
        (pid,),
    )
    row = cur.fetchone()
    conn.close()
    return row_to_prompt(row)


@router.put("/{prompt_id}", response_model=PromptOut)
def edit_prompt(prompt_id: int, prompt: PromptIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE prompts
        SET name = ?, description = ?, prompt = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (prompt.name, prompt.description, prompt.prompt, prompt_id),
    )
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Prompt not found")
    conn.commit()

    cur.execute(
        """
        SELECT id, name, description, prompt, created_at, updated_at
        FROM prompts
        WHERE id = ?
        """,
        (prompt_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row_to_prompt(row)


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.post("/{prompt_id}/run", response_model=PromptRunResponse)
async def run_prompt(prompt_id: int, cfg: PromptRunRequest):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT prompt FROM prompts WHERE id = ?", (prompt_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt_text: str = row["prompt"]

    payload = {
        "model": cfg.model,
        "prompt": prompt_text,
        "stream": False,
        "options": {"temperature": cfg.temperature},
    }

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    response_text = data.get("response", "")

    return PromptRunResponse(
        prompt_id=prompt_id,
        model=cfg.model,
        response=response_text,
    )
