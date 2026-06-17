from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from ollama import Client as OllamaClient

from lib.helper_ollama.scraper import scrape_library
from lib.helper_ollama.types import ModuleSize

from .client import Client
from .model import Model


class MODELS_SOURCE(Enum):
    web = "web"
    local = "local"
    both = "both"

SOURCE = MODELS_SOURCE


@dataclass
class Models:
    """
    Collection wrapper for multiple Model instances.

    Responsibilities:
    - collection queries (get, search, filters)
    - list + categories
    - installed views
    - bulk pulls
    """

    initial_models: Dict[str, Model] = field(default_factory=dict)
    _client: OllamaClient = field(init=False, repr=False)
    _models: Dict[str, Model] = field(init=False, repr=False)

    def __init__(
        self,
        source: MODELS_SOURCE = MODELS_SOURCE.both,
        *,
        models: Optional[Dict[str, Model]] = None,
        client: Optional[OllamaClient] = None,
    ) -> None:
        self._client = client or Client().client()
        if models is not None:
            self.initial_models = models
        else:
            self.initial_models = self._merge(source=source)
        self._models = self.initial_models

    # --- basics ---------------------------------------------------------

    def __iter__(self):
        return iter(self.initial_models.values())

    def __len__(self) -> int:
        return len(self.initial_models)

    def client(self) -> OllamaClient:
        return self._client

    def _collect_remote(self) -> Dict[str, Model]:
        payloads = scrape_library(self)
        models = [Model.from_dict(payload, client=self._client) for payload in payloads]
        return {model.name: model for model in models}

    def _collect_local(self) -> Dict[str, Model]:
        response = self._client.list()
        entries = getattr(response, "models", None)
        if entries is None:
            entries = getattr(response, "_models", None)
        if entries is None and hasattr(response, "get"):
            entries = response.get("models", [])
        if entries is None:
            entries = []

        grouped: Dict[str, List[ModuleSize]] = {}
        for entry in entries:
            name = (
                getattr(entry, "model", None) or entry.get("model") or entry.get("name")
            )
            if not name or ":" not in str(name):
                continue

            base, size = str(name).split(":", 1)
            sizes = grouped.setdefault(base, [])
            sizes.append(ModuleSize(size=size, installed=True))

        models: Dict[str, Model] = {}
        for base, sizes in grouped.items():
            models[base] = Model(
                name=base,
                installed=True,
                sizes=sizes,
                source="local",
                client=self._client,
            )
        return models

    def _merge(
        self,
        source: SOURCE,
    ) -> Dict[str, Model]:
        merged: Dict[str, Model] = {}
        remote = {}
        local = {}

        if source in (MODELS_SOURCE.web, MODELS_SOURCE.both):
            remote = self._collect_remote()
            merged.update(remote)

        if source in (MODELS_SOURCE.local, MODELS_SOURCE.both):
            local = self._collect_local()

        for base, local_model in local.items():
            if base in merged:
                existing = merged[base]
                existing.installed = True
                existing.source = "both"
                known_sizes = {size.size for size in existing.sizes}
                for size in local_model.sizes:
                    if size.size not in known_sizes:
                        existing.sizes.append(size)
            else:
                merged[base] = local_model

        return merged

    @classmethod
    def from_source(
        cls,
        *,
        source: MODELS_SOURCE = MODELS_SOURCE.both,
        client: Optional[OllamaClient] = None,
    ) -> "Models":
        return cls(source=source, client=client)

    # --- lookup ---------------------------------------------------------

    def get_by_name(self, name: str) -> Optional[Model]:
        return self.initial_models.get(name)

    def get(self, name: str) -> Optional[Model]:
        return self.get_by_name(name)

    # --- filtering ------------------------------------------------------

    def get_by_state(self, state: str) -> "Models":
        if not state or state == "all":
            return self

        target_state = state == "installed"
        filtered = {
            name: model
            for name, model in self.initial_models.items()
            if model.installed == target_state
        }
        return Models(models=filtered, client=self._client)

    def get_by_category(self, category: str) -> List[Model]:
        target = category.lower()
        return [
            m
            for m in self.initial_models.values()
            if any(c.lower() == target for c in m.categories)
        ]

    def get_by_categories(self, categories: Sequence[str]) -> "Models":
        if not categories:
            return self

        target = {cat.lower().strip() for cat in categories}
        filtered = {
            name: model
            for name, model in self.initial_models.items()
            if any(cat.lower() in target for cat in m.categories)
        }

        return Models(models=filtered, client=self._client)

    # --- listing --------------------------------------------------------

    def list_models(self, with_details: bool = False) -> Union["Models", List[str]]:
        if with_details:
            return self
        return self.get_names()

    def list(self, with_details: bool = False) -> Union["Models", List[str]]:
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

    # --- available / installed -----------------------------------------

    def get_available_model(self, name: str) -> Optional[Model]:
        return self.get_by_name(name)

    def get_available_categories(self) -> List[str]:
        return self.get_categories()

    def installed(self) -> List[Model]:
        return [m for m in self.initial_models.values() if m.installed]

    def refresh_installed_models(self) -> None:
        """Refresh only resets cached models (no helper)."""
        self.initial_models = self._merge(source=MODELS_SOURCE.both)
        self._models = self.initial_models

    def get_installed_models_with_details(self) -> "Models":
        """
        Combine local installed models with remote metadata where available.
        """
        local_map = self._collect_local()
        installed: Dict[str, Model] = {}

        for base, local_model in local_map.items():
            variants = local_model.local_variants
            installed_sizes = {size.size for size in local_model.sizes if size.size}

            remote_model = self.initial_models.get(base)
            if remote_model:
                model = Model.from_dict(remote_model.to_dict(), client=self._client)
                model.source = "both"
            else:
                model = Model(name=base, source="local", client=self._client)

            if remote_model or installed_sizes:
                if model.sizes and installed_sizes:
                    filtered = [
                        size for size in model.sizes if size in installed_sizes
                    ]
                    model.sizes = filtered or list(installed_sizes)
                    if "latest" in installed_sizes and "latest" not in model.sizes:
                        model.sizes.append(ModuleSize(size="latest", installed=True))
                elif installed_sizes:
                    model.sizes = list(installed_sizes)

            model.installed = True
            model.local_variants = variants
            installed[base] = model

        installed = dict(sorted(installed.items()))
        return Models(models=installed, client=self._client)

    # --- search ---------------------------------------------------------

    def search(self, text: str) -> List[Model]:
        needle = text.lower()
        return [
            m
            for m in self.initial_models.values()
            if needle in m.name.lower()
            or needle in m.description.lower()
            or any(needle in cat.lower() for cat in m.categories)
        ]

    # --- bulk operations ------------------------------------------------

    def pull(
        self,
        model_name: str,
        stream: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Pull a single model by name via a Model instance.
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
        Pull all given models (or all known, if names is None).
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

    # --- serialization --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {name: model.to_dict() for name, model in self.initial_models.items()}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        client: Optional[OllamaClient] = None,
    ) -> "Models":
        models = {
            name: Model.from_dict(data, client=client)
            for name, data in payload.items()
        }
        return cls(models=models, client=client)
