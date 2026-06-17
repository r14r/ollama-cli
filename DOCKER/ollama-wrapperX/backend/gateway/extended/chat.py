import os
import time
import uuid
import httpx

from typing import List, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.logging import log_prompt

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


async def call_ollama_chat(
    model: str,
    messages: List[ChatMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
    payload = {
        "model": model,
        "messages": ollama_messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens is not None:
        payload["options"]["num_predict"] = max_tokens

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    return data.get("message", {}).get("content", "")




@router.post("/completions", response_model=ChatCompletionResponse)
async def extended_chat_completions(req: ChatCompletionRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    last_user_msg = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        req.messages[-1].content,
    )

    t0 = time.time()
    assistant_text = await call_ollama_chat(
        model=req.model,
        messages=req.messages,
        temperature=req.temperature or 0.7,
        max_tokens=req.max_tokens,
    )
    duration = time.time() - t0

    log_prompt(req.model, last_user_msg, assistant_text, duration)

    created = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    choice = ChatCompletionChoice(
        index=0,
        message=ChatMessage(role="assistant", content=assistant_text),
        finish_reason="stop",
    )
    usage = ChatCompletionUsage()

    return ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=req.model,
        choices=[choice],
        usage=usage,
    )
