from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Dict,
    Final,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from ollama import Client as OllamaClient, ShowResponse, StatusResponse

from lib.helper_logging import debug
from lib.helper_ollama.types import ModuleSize

from .scraper import scrape_library

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_INSTALLED: Final[str] = "🟢"
STATUS_NOT_INSTALLED: Final[str] = "❌"

ICON_INSTALLED: Final[str] = "check-square"
ICON_NOT_INSTALLED: Final[str] = "square"

CATEGORY_ICONS = {
    "tools": "🧰",
    "vision": "👁️",
    "embedding": "🧩",
    "cloud": "☁️",
    "thinking": "🧠",
}

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "helper_ollama"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE_MODELS = CACHE_DIR / "models.json"
CACHE_TTL: Final[int] = 60 * 10  # 10 minutes


# ---------------------------------------------------------------------------
# Singleton Ollama Client
# ---------------------------------------------------------------------------

class Client:
    """
    Singleton wrapper around the Ollama SDK client.
    """

    _instance: Client | None = None
    _client: OllamaClient
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> Client:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    def __init__(self, host: Optional[str] = None) -> None:
        # Ensure we only initialize once
        if self._initialized:
            return

        self.host: str = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        client_kwargs: Dict[str, str] = {}
        if self.host:
            client_kwargs["host"] = self.host

        self._client = OllamaClient(**client_kwargs)
        self._initialized = True

    def client(self) -> OllamaClient:
        """Return the underlying Ollama SDK client."""
        return self._client


# ---------------------------------------------------------------------------
# Model – single model operations
# ---------------------------------------------------------------------------

class Model:
    """
    Representation of a single Ollama model/module with convenience methods
    for all model-related operations (show, delete, chat, pull, create, ...).
    """

    name: str

    slug: Optional[str] = None
    url: Optional[str] = None
    description: str = ""
    categories: Optional[List[str]] = None
    sizes: Optional[List[ModuleSize]] = None
    downloads: Optional[str] = None
    tags_count: Optional[int] = None
    updated: Optional[str] = None
    page: Optional[int] = None
    installed: bool = False
    local_variants: List[str] = field(default_factory=list)  # type: ignore[assignment]
    details: Dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]
    latest_this_session: bool = False
    source: Literal["remote", "local", "both"] = "remote"
    extras: Dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    _client: OllamaClient

    def __init__(
        self,
        name: str,
        extras: Optional[Mapping[str, Any]] = None,
        *,
        client: Optional[OllamaClient] = None,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.slug = kwargs.pop("slug", None)
        self.url = kwargs.pop("url", None)
        self.description = kwargs.pop("description", "")
        self.categories = list(kwargs.pop("categories", []) or [])
        self.sizes = list(kwargs.pop("sizes", []) or [])
        self.downloads = kwargs.pop("downloads", None)
        self.tags_count = kwargs.pop("tags_count", None)
        self.updated = kwargs.pop("updated", None)
        self.page = kwargs.pop("page", None)
        self.installed = bool(kwargs.pop("installed", False))
        self.local_variants = list(kwargs.pop("local_variants", []) or [])
        self.details = dict(kwargs.pop("details", {}) or {})
        self.latest_this_session = bool(kwargs.pop("latest_this_session", False))
        self.source = kwargs.pop("source", "remote") or "remote"
        extra_data = kwargs.pop("extras", None)

        if extras is not None:
            self.extras = dict(extras)
        else:
            self.extras = dict(extra_data or {})

        # Any remaining keys from payload become attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Injected or singleton Ollama client
        self._client = client or Client().client()

    # Low-level access ---------------------------------------------------

    def client(self) -> OllamaClient:
        return self._client

    # High-level operations ---------------------------------------------

    def show(self, **kwargs: Any) -> Mapping[str, Any]:
        """
        Fetch and cache full model details from Ollama.
        """
        info: ShowResponse = self.client().show(model=self.name, **kwargs)
        self.details = dict(info)
        return self.details

    def delete(self, **kwargs: Any) -> StatusResponse:
        """
        Delete the model in Ollama.
        """
        resp: StatusResponse = self.client().delete(model=self.name, **kwargs)
        self.installed = False
        self.local_variants.clear()
        return resp

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """
        Run a chat/completion against this model.
        """
        return self.client().chat(model=self.name, messages=messages, **kwargs)  # type: ignore[return-value]

    def copy(self, new_name: str, **kwargs: Any) -> StatusResponse:
        """
        Copy/tag this model to a new name.
        """
        return self.client().copy(source=self.name, target=new_name, **kwargs)

    def generate(self, **kwargs: Any) -> Mapping[str, Any]:
        """
        Run a generate/completion call against this model.
        """
        return self.client().generate(model=self.name, **kwargs)  # type: ignore[return-value]

    def pull(self, stream: bool = True, **kwargs: Any) -> Any:
        """
        Pull/install this model via the Ollama API.
        """
        debug(f"Pulling model {self.name} with stream={stream} and kwargs={kwargs}")

        try:
            response = self.client().pull(model=self.name, stream=stream, **kwargs)
        except Exception as exc:
            debug(f"Error pulling model {self.name}: {exc}")
            raise

        return response

    def create(
        self,
        modelfile: str,
        stream: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Create/build this model from a Modelfile.
        """
        return self.client().create(
            model=self.name,
            template=modelfile,
            stream=stream,
            **kwargs,
        )

    # Serialization helpers ---------------------------------------------

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        client: Optional[OllamaClient] = None,
    ) -> Model:
        annotations = getattr(cls, "__annotations__", {})
        known = [name for name in annotations if name != "extras"]

        extras = {k: v for k, v in payload.items() if k not in known}

        init: Dict[str, Any] = {k: payload.get(k) for k in known}
        init["categories"] = list(init.get("categories") or [])
        init["sizes"] = list(init.get("sizes") or [])

        return cls(extras=extras, client=client, **init)

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        sizes = data.get("sizes")
        if isinstance(sizes, list):
            normalized: List[Dict[str, Any]] = []
            for entry in sizes:
                if isinstance(entry, ModuleSize):
                    normalized.append(entry.to_dict())
                elif isinstance(entry, dict):
                    normalized.append(entry)
                else:
                    normalized.append(
                        {
                            "size": str(entry),
                            "installed": bool(
                                getattr(entry, "installed", False)
                            ),
                        }
                    )
            data["sizes"] = normalized
        return data

    # Convenience property -----------------------------------------------

    @property
    def base_name(self) -> str:
        """
        Model name without variant tag (i.e. 'llama3:8b' -> 'llama3').
        """
        return self.name.split(":", 1)[0]


# ---------------------------------------------------------------------------
# Models – collection of Model objects
# ---------------------------------------------------------------------------

@dataclass
class Models:
    """
    Collection-type wrapper for multiple Model instances.
    Provides search/filter/list operations.
    """

    initial_models: Dict[str, Model] = field(default_factory=dict)
    helper: Optional["Helper"] = field(default=None, repr=False)

    _client: OllamaClient = field(init=False, repr=False)

    def __init__(
        self,
        initial_models: Optional[Dict[str, Model]] = None,
        helper: Optional["Helper"] = None,
        *,
        client: Optional[OllamaClient] = None,
    ) -> None:
        self.initial_models = initial_models or {}
        self.helper = helper
        self._client = client or Client().client()

    # Basic protocol -----------------------------------------------------

    def __iter__(self):
        return iter(self.initial_models.values())

    def __len__(self) -> int:
        return len(self.initial_models)

    def client(self) -> OllamaClient:
        return self._client

    # Lookup -------------------------------------------------------------

    def get_by_name(self, name: str) -> Optional[Model]:
        return self.initial_models.get(name)

    def get(self, name: str) -> Optional[Model]:
        return self.get_by_name(name)

    # Filtering ----------------------------------------------------------

    def get_by_state(self, state: str) -> Models:
        if not state or state == "all":
            return self

        target_state = state == "installed"
        filtered = {
            name: model
            for name, model in self.initial_models.items()
            if model.installed == target_state
        }
        return Models(initial_models=filtered, helper=self.helper, client=self._client)

    def get_by_category(self, category: str) -> List[Model]:
        target = category.lower()
        return [
            m
            for m in self.initial_models.values()
            if any(c.lower() == target for c in m.categories)
        ]

    def get_by_categories(self, categories: Sequence[str]) -> Models:
        if not categories:
            return self

        target = {cat.lower().strip() for cat in categories}
        filtered = {
            name: model
            for name, model in self.initial_models.items()
            if any(cat.lower() in target for cat in model.categories)
        }

        return Models(initial_models=filtered, helper=self.helper, client=self._client)

    # Listing ------------------------------------------------------------

    def list_models(self, with_details: bool = False) -> Union[Models, List[str]]:
        if with_details:
            return self
        return self.get_names()

    def list(self, with_details: bool = False) -> Union[Models, List[str]]:
        return self.list_models(with_details=with_details)

    def get_names(self) -> List[str]:
        return list(self.initial_models.keys())

    def get_categories(self) -> List[str]:
        cats: set[str] = set()
        for model in self.initial_models.values():
            for category in model.categories:
                if category:
                    cats.add(category.lower())
        return sorted(cats)

    # Installed / available ----------------------------------------------

    def installed(self) -> List[Model]:
        return [m for m in self.initial_models.values() if m.installed]

    def refresh_installed_models(self) -> None:
        """
        Ask the Helper (if present) to refresh its caches.
        """
        if self.helper:
            self.helper.refresh()
            self.helper.get_models(use_cache=False)

    def get_installed_models_with_details(self) -> Models:
        """
        Build a Models instance containing only installed models (local),
        merged with remote metadata where available.
        """
        if not self.helper:
            return Models(initial_models={}, helper=None, client=self._client)

        local_map = self.helper._get_local()
        installed: Dict[str, Model] = {}

        for base, info in local_map.items():
            variants = info.get("variants", [])
            installed_sizes = {
                variant.split(":", 1)[1].lower()
                if ":" in variant
                else variant.lower()
                for variant in variants
                if variant
            }

            remote_model = self.initial_models.get(base)
            if remote_model:
                model = Model.from_dict(
                    remote_model.to_dict(),
                    client=self._client,
                )
                model.source = "both"
            else:
                model = Model(name=base, source="local", client=self._client)

            if remote_model or installed_sizes:
                if model.sizes and installed_sizes:
                    filtered_sizes = [
                        size for size in model.sizes if size in installed_sizes
                    ]
                    model.sizes = filtered_sizes or list(installed_sizes)
                    if "latest" in installed_sizes and "latest" not in model.sizes:
                        model.sizes.append(
                            ModuleSize(size="latest", installed=True)
                        )
                elif installed_sizes:
                    model.sizes = list(installed_sizes)

            model.installed = True
            model.local_variants = variants
            installed[base] = model

        installed = dict(sorted(installed.items()))
        return Models(initial_models=installed, helper=self.helper, client=self._client)

    # Search -------------------------------------------------------------

    def search(self, text: str) -> List[Model]:
        needle = text.lower()
        return [
            m
            for m in self.initial_models.values()
            if needle in m.name.lower()
            or needle in m.description.lower()
            or any(needle in cat.lower() for cat in m.categories)
        ]

    # Bulk operations ----------------------------------------------------

    def pull(
        self,
        model_name: str,
        stream: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Pull a single model by name.
        """
        return Model(name=model_name, client=self._client).pull(
            stream=stream,
            **kwargs,
        )

    def pull_all(
        self,
        names: Optional[Sequence[str]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Pull all given models (or all known if names is None).
        """
        result: Dict[str, Any] = {}
        targets = names if names is not None else self.get_names()

        for name in targets:
            model = self.initial_models.get(name)
            if not model:
                result[name] = {"error": "unknown model"}
                continue
            try:
                resp = Model(name, client=self._client).pull(
                    stream=stream,
                    **kwargs,
                )
                result[name] = resp
                model.installed = True
                model.latest_this_session = True
            except Exception as exc:
                result[name] = {"error": str(exc)}
        return result

    # Serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {name: model.to_dict() for name, model in self.initial_models.items()}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        helper: Optional["Helper"] = None,
        *,
        client: Optional[OllamaClient] = None,
    ) -> Models:
        models = {
            name: Model.from_dict(data, client=client)
            for name, data in payload.items()
        }
        return cls(initial_models=models, helper=helper, client=client)


# ---------------------------------------------------------------------------
# Helper – orchestration, caching, local + remote model collection
# ---------------------------------------------------------------------------

class Helper:
    """
    Facade around Client / Models / Model with:
    - local model list (via Ollama list)
    - remote model list (via scraping)
    - caching (memory + disk)
    """

    def __init__(self, *, client: Optional[OllamaClient] = None) -> None:
        self._client: OllamaClient = client or Client().client()
        self._remote_cache: Optional[Tuple[float, Models]] = None
        self._models: Optional[Models] = None
        self._model: Optional[Model] = None

    # Low-level client ---------------------------------------------------

    def client(self) -> OllamaClient:
        return self._client

    # Cache helpers ------------------------------------------------------

    def _cache_payload(self) -> Dict[str, Any]:
        if not self._remote_cache:
            return {}
        ts, models = self._remote_cache
        return {"ts": ts, "models": models.to_dict()}

    def _load_from_disk(self, use_cache: bool) -> Optional[Models]:
        if not use_cache or not CACHE_FILE_MODELS.exists():
            return None
        try:
            payload = json.loads(CACHE_FILE_MODELS.read_text())
            ts = payload.get("ts", 0)
            models_data = payload.get("models", {})
            if time.time() - ts > CACHE_TTL:
                return None
            models = Models.from_dict(
                models_data,
                helper=self,
                client=self._client,
            )
            self._remote_cache = (ts, models)
            return models
        except Exception:
            return None

    def _save_to_disk(self) -> None:
        try:
            payload = self._cache_payload()
            if payload:
                CACHE_FILE_MODELS.write_text(json.dumps(payload))
        except Exception:
            # Do not fail on cache write errors
            pass

    # Local models -------------------------------------------------------

    def _get_local(self) -> Dict[str, Dict[str, Any]]:
        """
        Query Ollama for local models and normalize result into a dict structure.
        """
        response = self.client().list()
        entries = response.get("models", [])

        models: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            # Ollama list() returns objects with .model or ['model'] depending on version
            name = entry.get("model") or entry.get("name")
            if not name:
                continue

            base, size = str(name).split(":", 1)
            sizes = models.setdefault(base, {"sizes": []})
            sizes["sizes"].append(ModuleSize(size=size, installed=True))

        return models

    # Remote models via scraping ----------------------------------------

    def _scrape_library(
        self,
        sort: str = "popular",
        query: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Models:
        payloads = scrape_library(self, content=content)
        models = [
            Model.from_dict(payload, client=self._client)
            for payload in payloads
        ]
        return Models(
            initial_models={model.name: model for model in models},
            helper=self,
            client=self._client,
        )

    def _get_remote_models(
        self,
        sort: str,
        query: Optional[str],
        use_cache: bool,
    ) -> Models:
        now = time.time()

        # In-memory cache
        if use_cache and self._remote_cache:
            ts, models = self._remote_cache
            if now - ts < CACHE_TTL:
                return models

        # Disk cache
        disk = self._load_from_disk(use_cache)
        if disk:
            return disk

        # Fresh scrape
        models = self._scrape_library(sort=sort, query=query)

        self._remote_cache = (now, models)
        self._save_to_disk()
        return models

    # Public API – models collection ------------------------------------

    def get_models(
        self,
        sort: str = "popular",
        query: Optional[str] = None,
        use_cache: bool = True,
    ) -> Models:
        """
        Merge remote and local models into a unified Models collection.
        """
        remote = self._get_remote_models(sort=sort, query=query, use_cache=use_cache)
        local = self._get_local()

        merged: Dict[str, Model] = dict(remote.initial_models)

        for base, local_model in local.items():
            if base in merged:
                model = merged[base]
                model.installed = True

                local_model_sizes = [size.size for size in local_model["sizes"]]

                # Step 1: collect all sizes
                all_sizes = {m.size for m in model.sizes} | set(local_model_sizes)

                # Step 2: rebuild objects (preserve installed=True if already present)
                installed_map = {m.size: m.installed for m in model.sizes}

                model.sizes = [
                    ModuleSize(size=s, installed=installed_map.get(s, True))
                    for s in sorted(all_sizes)  # optional sort
                ]

                model.source = "both"
            else:
                merged[base] = Model(
                    name=base,
                    installed=True,
                    sizes=local_model["sizes"],
                    source="local",
                    client=self._client,
                )

        result = Models(initial_models=merged, helper=self, client=self._client)

        return result

    def refresh(self) -> None:
        """
        Clear caches (memory + disk). Next call to get_models() will reload.
        """
        self._remote_cache = None
        self._models = None
        if CACHE_FILE_MODELS.exists():
            CACHE_FILE_MODELS.unlink()

    # Convenience wrappers ----------------------------------------------

    def get_available_models_with_details(
        self,
        **kwargs: Any,
    ) -> Models:
        models = self.get_models(**kwargs)
        self._models = models
        return models

    def get_available_model(self, name: str, **kwargs: Any) -> Optional[Model]:
        models = self.get_models(**kwargs)
        self._models = models
        return models.get(name)

    def get_available_categories(self, **kwargs: Any) -> List[str]:
        models = self.get_models(**kwargs)
        self._models = models
        return models.get_categories()

    def get_installed_models_with_details(self, **kwargs: Any) -> Models:
        models = self.get_models(**kwargs)
        self._models = models
        return models.get_installed_models_with_details()

    def get_installed_models_names(self, **kwargs: Any) -> List[str]:
        return self.get_installed_models_with_details(**kwargs).get_names()

    # Properties: unified access ----------------------------------------

    @property
    def models(self) -> Models:
        """
        Lazily cached full Models collection (remote + local).
        """
        if self._models is None:
            self._models = self.get_available_models_with_details()
        return self._models

    def model(self, name: str, **kwargs: Any) -> Optional[Model]:
        """
        Convenience: get a single model by name, caching the collection.
        """
        models = self.get_models(**kwargs)
        self._models = models
        self._model = models.get(name)
        return self._model


# Global helper instance -------------------------------------------------

helper = Helper()

__all__ = [
    "helper",
    "Helper",
    "Model",
    "Models",
    "scrape_library",
    "STATUS_INSTALLED",
    "STATUS_NOT_INSTALLED",
    "ICON_INSTALLED",
    "ICON_NOT_INSTALLED",
    "CATEGORY_ICONS",
]
