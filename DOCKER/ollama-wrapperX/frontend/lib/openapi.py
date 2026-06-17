"""Central location for the runtime URLs/paths that the UI calls."""

from __future__ import annotations

import os
from dataclasses import dataclass


OLLAMA_OPENAPI_URL = os.getenv("OLLAMA_URL_PUBLIC", "http://localhost:11434").rstrip("/")
GATEWAY_OPENAPI_URL = os.getenv("GATEWAY_URL_PUBLIC", "http://localhost:8000").rstrip("/")


@dataclass(frozen=True)
class ExtendedChatEndpoints(str):
    completions: str = "/extended/chat/completions"


@dataclass(frozen=True)
class ExtendedModelsEndpoints(str):
    root: str = "/extended/models"
    running: str = "/extended/models/running"


@dataclass(frozen=True)
class ExtendedPromptsEndpoints(str):
    root: str = "/extended/prompts"
    recent: str = "/extended/prompts/recent"
    detail: str = "/extended/prompts/{prompt_id}"
    run: str = "/extended/prompts/{prompt_id}/run"


@dataclass(frozen=True)
class ExtendedTemplatesEndpoints(str):
    root: str = "/extended/templates"
    detail: str = "/extended/templates/{template_id}"
    run: str = "/extended/templates/{template_id}/run"


@dataclass(frozen=True)
class ExtendedMonitoringStatusEndpoints(str):
    status: str = "/extended/monitoring/status"

@dataclass(frozen=True)
class ExtendedMonitoringHealthEndpoints(str):
    status: str = "/extended/monitoring/health"

@dataclass(frozen=True)
class ExtendedEndpoints(str):
    health: ExtendedMonitoringHealthEndpoints = ExtendedMonitoringHealthEndpoints()
    chat: ExtendedChatEndpoints = ExtendedChatEndpoints()
    models: ExtendedModelsEndpoints = ExtendedModelsEndpoints()
    prompts: ExtendedPromptsEndpoints = ExtendedPromptsEndpoints()
    templates: ExtendedTemplatesEndpoints = ExtendedTemplatesEndpoints()
    monitoring_status: ExtendedMonitoringStatusEndpoints = ExtendedMonitoringStatusEndpoints()


EXTENDED = ExtendedEndpoints()


__all__ = [
    "OLLAMA_OPENAPI_URL",
    "GATEWAY_OPENAPI_URL",
    "ExtendedEndpoints",
    "ExtendedChatEndpoints",
    "ExtendedModelsEndpoints",
    "ExtendedPromptsEndpoints",
    "ExtendedTemplatesEndpoints",
    "ExtendedMonitoringStatusEndpoints",
    "EXTENDED",
]
