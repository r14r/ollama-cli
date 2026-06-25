from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest
from ollama import Client as OllamaClient

from lib.helper_ollama.client import Client
from lib.helper_ollama.model import Model
from lib.helper_ollama.types import ModuleSize

ROOT = Path(__file__).resolve().parents[3]
ENV_TEST_FILE = ROOT / ".env.pytest"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    with path.open() as envfile:
        for line in envfile:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            if not key:
                continue
            os.environ.setdefault(key.strip(), value.strip().strip('"\'' ))


_load_env_file(ENV_TEST_FILE)

OLLAMA_TEST_PREINSTALLED_MODEL=os.getenv("OLLAMA_TEST_PREINSTALLED_MODEL")
OLLAMA_TEST_UNINSTALLED_MODEL=os.getenv("OLLAMA_TEST_UNINSTALLED_MODEL")

@pytest.fixture(scope="session")
def ollama_client() -> OllamaClient:
    return Client().client()


@pytest.fixture(scope="session")
def ollama_preinstalled_model() -> str:
    return OLLAMA_TEST_PREINSTALLED_MODEL

@pytest.fixture
def model(ollama_client: OllamaClient, ollama_preinstalled_model: str) -> Model:
    return Model(
        name=ollama_preinstalled_model,
        description=f"Preinstalled Model {OLLAMA_TEST_PREINSTALLED_MODEL} for pytest",
        categories=["test"],
        sizes=[ModuleSize(size="test", installed=True)],
        installed=True,
        details={},
        source="remote",
        client=ollama_client,
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_preinstalledmodels(ollama_client: OllamaClient) -> Iterator[None]:
    model = Model(name=OLLAMA_TEST_PREINSTALLED_MODEL, client=ollama_client)
    try:
        response = model.pull(stream=False)  # noqa: F841
        model.installed = True
    except Exception:
        pass
    yield


@pytest.fixture(scope="session", autouse=True)
def ensure_uninstalled_models(ollama_client: OllamaClient) -> Iterator[None]:
    model = Model(name=OLLAMA_TEST_UNINSTALLED_MODEL, client=ollama_client)
    try:
        response = model.delete()  # noqa: F841
    except Exception:
        pass
    yield


@pytest.fixture(scope="session")
def tmp_model_name() -> str:
    return os.getenv("OLLAMA_TEST_TMP_MODEL", "pytest-temp-model")


@pytest.fixture(scope="session")
def base_model_for_create() -> str:
    return os.getenv("OLLAMA_TEST_BASE_MODEL", "llama3")


@pytest.fixture
def tmp_model(
    ollama_client: OllamaClient,
    tmp_model_name: str,
    base_model_for_create: str,
) -> Iterator[Model]:
    allow_mutation = os.getenv("OLLAMA_TEST_ALLOW_MUTATION", "0") == "1"
    m = Model(
        name=tmp_model_name,
        description="Temporary pytest model",
        categories=["test"],
        sizes=[],
        installed=False,
        details={},
        source="remote",
        client=ollama_client,
    )

    if not allow_mutation:
        yield m
        return

    modelfile = f"FROM {base_model_for_create}\nPARAM temperature 0.0"
    m.create(modelfile=modelfile, stream=False)
    m.installed = True

    try:
        yield m
    finally:
        try:
            m.delete()
        except Exception:
            pass


@pytest.fixture
def dict_payload(ollama_preinstalled_model: str) -> dict:
    return {
        "name": ollama_preinstalled_model,
        "slug": "test-model",
        "url": "http://example.com/models/test-model",
        "description": "Description",
        "categories": ["tools", "vision"],
        "sizes": [ModuleSize(size="8b", installed=False).to_dict()],
        "downloads": "123",
        "tags_count": 5,
        "updated": "2025-01-01",
        "page": 42,
        "installed": True,
        "local_variants": [f"{ollama_preinstalled_model}:8b"],
        "details": {"a": 1},
        "latest_this_session": True,
        "source": "remote",
        "extras": {"meta": "x"},
        "unknown_field": "should_end_up_in_extras",
    }
