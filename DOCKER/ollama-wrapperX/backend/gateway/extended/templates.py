import os
import httpx
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .db import get_connection

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

router = APIRouter()


class TemplateIn(BaseModel):
    name: str = Field(..., description="Name of the system prompt template")
    description: Optional[str] = None
    content: str = Field(..., description="System prompt text")
    tags: Optional[List[str]] = None


class TemplateOut(TemplateIn):
    id: int
    created_at: str
    updated_at: str


class TemplateRunRequest(BaseModel):
    model: str = "llama3"
    user_input: str = Field(..., description="User message to send together with system template")
    temperature: float = 0.7


class TemplateRunResponse(BaseModel):
    template_id: int
    model: str
    system_prompt: str
    user_input: str
    response: str


def row_to_template(row) -> TemplateOut:
    return TemplateOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        content=row["content"],
        tags=row["tags"].split(",") if row["tags"] else [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/", response_model=List[TemplateOut])
def list_templates():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, description, content, tags, created_at, updated_at
        FROM templates
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [row_to_template(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, description, content, tags, created_at, updated_at
        FROM templates
        WHERE id = ?
        """,
        (template_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return row_to_template(row)


@router.post("/", response_model=TemplateOut)
def save_template(template: TemplateIn):
    conn = get_connection()
    cur = conn.cursor()
    tags_str = ",".join(template.tags) if template.tags else None
    cur.execute(
        """
        INSERT INTO templates (name, description, content, tags)
        VALUES (?, ?, ?, ?)
        """,
        (template.name, template.description, template.content, tags_str),
    )
    tid = cur.lastrowid
    conn.commit()

    cur.execute(
        """
        SELECT id, name, description, content, tags, created_at, updated_at
        FROM templates
        WHERE id = ?
        """,
        (tid,),
    )
    row = cur.fetchone()
    conn.close()
    return row_to_template(row)


@router.put("/{template_id}", response_model=TemplateOut)
def edit_template(template_id: int, template: TemplateIn):
    conn = get_connection()
    cur = conn.cursor()
    tags_str = ",".join(template.tags) if template.tags else None
    cur.execute(
        """
        UPDATE templates
        SET name = ?, description = ?, content = ?, tags = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (template.name, template.description, template.content, tags_str, template_id),
    )
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")
    conn.commit()

    cur.execute(
        """
        SELECT id, name, description, content, tags, created_at, updated_at
        FROM templates
        WHERE id = ?
        """,
        (template_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row_to_template(row)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Template not found")


@router.post("/{template_id}/run", response_model=TemplateRunResponse)
async def run_template(template_id: int, cfg: TemplateRunRequest):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT content FROM templates WHERE id = ?", (template_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    system_prompt: str = row["content"]

    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": cfg.user_input},
        ],
        "stream": False,
        "options": {"temperature": cfg.temperature},
    }

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)

    if resp.status_code != 0 and resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    response_text = data.get("message", {}).get("content", "")

    return TemplateRunResponse(
        template_id=template_id,
        model=cfg.model,
        system_prompt=system_prompt,
        user_input=cfg.user_input,
        response=response_text,
    )
