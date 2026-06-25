# ---------------------------------------------------------------------------
# Singleton Ollama client wrapper
# ---------------------------------------------------------------------------
from __future__ import annotations

import os
from typing import (
    Dict,
    Optional,
)

from ollama import Client as OllamaClient,  ShowResponse, StatusResponse, ChatResponse, GenerateResponse, ResponseError


class Client:
    """
    Singleton wrapper around ollama.Client.
    """

    _instance: Client | None = None
    _client: OllamaClient
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> Client:
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance  # type: ignore[return-value]

    def __init__(self, host: Optional[str] = None) -> None:
        if self._initialized:
            return

        # Determine host (prefers OLLAMA_URL to fit your current config)
        self.host: str = host or os.environ.get("OLLAMA_URL", "http://localhost:11434")

        client_kwargs: Dict[str, str] = {}
        if self.host:
            client_kwargs["host"] = self.host

        self._client = OllamaClient(**client_kwargs)
        self._initialized = True

    def client(self) -> OllamaClient:
        """Return the underlying Ollama SDK client."""
        return self._client



__all__ = [
    "Client",
    "ShowResponse",
    "StatusResponse",
    "ChatResponse",
    "GenerateResponse",
    "ResponseError"
]
