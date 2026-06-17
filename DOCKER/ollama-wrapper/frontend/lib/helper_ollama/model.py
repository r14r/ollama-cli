# model.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence

from lib.helper_logging import debug

from .types import RESPONSESTATES, ModuleSize, ResponseState
from .client import Client, ShowResponse, StatusResponse, ResponseError


class Model:
    """
    Representation of a single Ollama model/module with all model-related
    operations (show, delete, chat, copy, generate, pull, create).
    """

    # Type hints for introspection / tooling (no dataclass here)
    name: str
    slug: Optional[str]
    url: Optional[str]
    description: str
    categories: List[str]
    sizes: List[ModuleSize] | List[Dict[str, Any]]
    downloads: Optional[str]
    tags_count: Optional[int]
    updated: Optional[str]
    page: Optional[int]
    installed: bool
    details: Dict[str, Any]
    latest_this_session: bool
    source: Literal["remote", "local", "both"]
    extras: Dict[str, Any]

    _client: Client

    def __init__(
        self,
        name: str = None,
        extras: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.name = name

        # Known fields with normalization
        self.slug = kwargs.pop("slug", None)
        self.url = kwargs.pop("url", None)
        self.description = kwargs.pop("description", "") or ""
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

        # Extras handling: explicit extras param wins
        extra_data = kwargs.pop("extras", None)
        if extras is not None:
            self.extras = dict(extras)
        else:
            self.extras = dict(extra_data or {})

        # Any remaining unknown keys become attributes (forward compatibility)
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Injected or singleton client
        self._client = Client().client()

    # --- model operations -----------------------------------------------
    def show(self, **kwargs: Any) -> ResponseState:
        """
        Fetch and cache full model details from Ollama.
        """
        response: ShowResponse | None = None
        state: ResponseState | None = None

        try:
            response = self._client.show(model=self.name, **kwargs)
            self.details = dict(response)
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=response,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    def run(self, **kwargs: Any) -> ResponseState:
        raise RuntimeError("TO BE IMPLEMENTED")

    def delete(self, **kwargs: Any) -> ResponseState:
        """
        Delete this model in Ollama.
        """
        r: StatusResponse | None = None
        state: ResponseState | None = None

        try:
            r = self._client.delete(model=self.name, **kwargs)
            self.installed = False
            self.local_variants.clear()
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=r,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        stream: bool = False,
        temperature: int = None,
    ) -> ResponseState:
        """
        Run a chat/completion against this model.
        """
        r: Mapping[str, Any] | None = None
        state: ResponseState | None = None

        options = {}
        if temperature is not None:
            options = {"temperature": temperature}

        try:
            r = self._client.chat(
                model=self.name,
                messages=messages,
                options=options,
                stream=stream,
            )
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=r,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    # Generate:
    # response = generate('gemma3', 'Why is the sky blue?')
    # print(response['response'])
    #
    # Generate with stream=True
    # for part in generate('gemma3', 'Why is the sky blue?', stream=True):
    #     print(part['response'], end='', flush=True)

    def generate(
        self,
        prompt: str,
        stream: bool = False,
        temperature: int = None,
    ) -> ResponseState:
        """
        Run a generate against this model.
        """
        r: Mapping[str, Any] | None = None
        state: ResponseState | None = None

        options = {}
        if temperature is not None:
            options = {"temperature": temperature}

        try:
            r = self._client.generate(
                model=self.name, prompt=prompt, options=options, stream=stream
            )
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=r,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    def pull(self, stream: bool = False, **kwargs: Any) -> ResponseState:
        """
        Pull/install this model via the Ollama API.
        """
        debug(f"Pulling model {self.name} with stream={stream} and kwargs={kwargs}")
        response: Any | None = None
        state: ResponseState | None = None

        try:
            response = self._client.pull(model=self.name, stream=stream, **kwargs)
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message=response.status,
                response=response,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            debug(f"Error pulling model {self.name}: {e}")
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    def push(self, **kwargs: Any) -> ResponseState:
        raise RuntimeError("TO BE IMPLEMENTED")

    # --- copy -------------------------------------------------------

    def copy(self) -> ResponseState:
        """
        Copy/tag this model to a new name.
        """
        r: StatusResponse | None = None
        state: ResponseState | None = None

        try:
            r = self._client.copy(model=self.name)
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=r,
            )
        except ResponseError as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=e.error,
                response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state

    def create(self, name: str, modelfile: str, stream: bool = True) -> ResponseState:
        """
        Create/build this model from a Modelfile.
        """
        r: Any | None = None
        state: ResponseState | None = None

        try:
            r = self._client.create(model=name, template=modelfile, stream=stream)
            state = ResponseState(
                state=RESPONSESTATES.OK,
                message="",
                response=r,
            )
        except ResponseError as e:
            state = ResponseState(state=RESPONSESTATES.ERROR, message=e.error, response=e,
            )
        except Exception as e:
            state = ResponseState(
                state=RESPONSESTATES.ERROR,
                message=str(e),
                response=e,
            )

        return state


    # --- serialization helpers -----------------------------------------

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        client: Optional[Client] = None,
    ) -> "Model":
        """
        Build a Model from a dict payload (e.g. scraper result or cache).

        Known keys become first-class fields; unknown keys end up in `extras`.
        """
        # Known top-level fields (excluding internal/private ones)
        known_fields = {
            "name",
            "slug",
            "url",
            "description",
            "categories",
            "sizes",
            "downloads",
            "tags_count",
            "updated",
            "page",
            "installed",
            "local_variants",
            "details",
            "latest_this_session",
            "source",
            "extras",
        }

        # Required
        name = payload.get("name")
        if not name:
            raise ValueError("Model.from_dict() requires a 'name' field in payload")

        # Extras = everything not in known_fields
        extras = {k: v for k, v in payload.items() if k not in known_fields}

        # Init kwargs = intersection of payload & known_fields (excluding name & extras)
        init_kwargs: Dict[str, Any] = {
            k: payload.get(k)
            for k in known_fields
            if k not in {"name", "extras"} and k in payload
        }

        # Normalize list-like fields
        init_kwargs["categories"] = list(init_kwargs.get("categories") or [])
        init_kwargs["sizes"] = list(init_kwargs.get("sizes") or [])

        return cls(
            name=name,
            extras=payload.get("extras", extras),
            client=client,
            **init_kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Model into a dict suitable for JSON/cache.

        Internal attributes like `_client` are omitted.
        """
        data: Dict[str, Any] = {
            "name": self.name,
            "slug": self.slug,
            "url": self.url,
            "description": self.description,
            "categories": list(self.categories or []),
            "sizes": [],
            "downloads": self.downloads,
            "tags_count": self.tags_count,
            "updated": self.updated,
            "page": self.page,
            "installed": self.installed,
            "local_variants": list(self.local_variants or []),
            "details": dict(self.details or {}),
            "latest_this_session": self.latest_this_session,
            "source": self.source,
            "extras": dict(self.extras or {}),
        }

        # Normalize sizes list
        sizes_out: List[Dict[str, Any]] = []
        for entry in self.sizes or []:
            if isinstance(entry, ModuleSize):
                sizes_out.append(entry.to_dict())
            elif isinstance(entry, dict):
                sizes_out.append(entry)
            else:
                sizes_out.append(
                    {
                        "size": str(entry),
                        "installed": bool(getattr(entry, "installed", False)),
                    }
                )
        data["sizes"] = sizes_out

        return data

    # --- convenience ----------------------------------------------------

    @property
    def base_name(self) -> str:
        """
        Model name without variant tag (e.g. 'llama3:8b' -> 'llama3').
        """
        return self.name.split(":", 1)[0]
