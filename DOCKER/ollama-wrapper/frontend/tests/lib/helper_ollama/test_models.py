from __future__ import annotations

from typing import Any, Dict, List

import pytest

from lib.helper_ollama.models import MODELS_SOURCE, Models
from lib.helper_ollama.types import ModuleSize


class ClientListEntry:
    def __init__(self, model: str) -> None:
        self.model = model


class ClientListResponse:
    def __init__(self, names: List[str]) -> None:
        self.models = [ClientListEntry(name) for name in names]

    def get(self, key: str, default: Any = None) -> Any:
        if key == "models":
            return self.models
        return default


class TestClient:
    __test__ = False

    def __init__(self, local_models: List[str], use_ollama: bool = False) -> None:
        self._models = local_models
        self.use_ollama = use_ollama
        self._client = None

        if self.use_ollama:
            from lib.helper_ollama.client import Client as OllamaClientWrapper

            self._client = OllamaClientWrapper().client()

    def list(self) -> ClientListResponse:
        if self.use_ollama and self._client is not None:
            return self._client.list()
        return ClientListResponse(self._models)


def _remote_payload() -> List[Dict[str, Any]]:
    return [
        {
            "name": "remote-1",
            "description": "First remote model",
            "categories": ["tools"],
            "sizes": [ModuleSize(size="8b", installed=False)],
            "installed": False,
            "source": "remote",
            "extras": {},
            "local_variants": [],
            "details": {},
            "latest_this_session": False,
            "slug": "remote-1",
            "url": "https://example.com/remote-1",
        },
        {
            "name": "remote-2",
            "description": "Second remote model",
            "categories": ["vision"],
            "sizes": [ModuleSize(size="base", installed=False)],
            "installed": False,
            "source": "remote",
            "extras": {},
            "local_variants": [],
            "details": {},
            "latest_this_session": False,
            "slug": "remote-2",
            "url": "https://example.com/remote-2",
        },
    ]


@pytest.fixture
def remote_models(monkeypatch: Any) -> Any:
    def fake_scrape(helper: Any, content: str | None = None) -> List[Dict[str, Any]]:
        return _remote_payload()

    monkeypatch.setattr("lib.helper_ollama.models.scrape_library", fake_scrape)
    return fake_scrape


def test_extracting_local_models_with_testclient() -> None:
    client = TestClient(["local-one:8b", "local-two:latest"])
    models = Models.from_source(source=MODELS_SOURCE.local, client=client)

    assert set(models.get_names()) == {"local-one", "local-two"}
    assert all(model.installed for model in models.initial_models.values())
    assert all(model.source == "local" for model in models.initial_models.values())


def test_extracting_local_models() -> None:
    client = TestClient(["gemma3:latest", "phi4-mini:8b"])
    models = Models(source=MODELS_SOURCE.local, client=client)

    assert set(models.get_names()) == {"gemma3", "phi4-mini"}
    assert all(model.installed for model in models.initial_models.values())
    assert all(model.source == "local" for model in models.initial_models.values())


def test_extracting_remote_models(remote_models: Any) -> None:
    client = TestClient([])
    models = Models.from_source(source=MODELS_SOURCE.web, client=client)

    assert set(models.get_names()) == {"remote-1", "remote-2"}
    assert all(model.source == "remote" for model in models.initial_models.values())
    assert all(not model.installed for model in models.initial_models.values())


def test_extracting_all_models(remote_models: Any) -> None:
    client = TestClient(["remote-1:8b", "local-extra:latest"])
    models = Models.from_source(source=MODELS_SOURCE.both, client=client)

    assert set(models.get_names()) == {"remote-1", "remote-2", "local-extra"}

    shared = models.initial_models["remote-1"]
    assert shared.installed is True
    assert shared.source == "both"
    assert any(size.size == "8b" for size in shared.sizes)

    local_only = models.initial_models["local-extra"]
    assert local_only.source == "local"
    assert local_only.installed is True


def test_count_extracted_models(remote_models: Any) -> None:
    client = TestClient(["local-five:latest"])
    models = Models.from_source(source=MODELS_SOURCE.both, client=client)

    assert len(models) == 3
