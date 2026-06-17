from dataclasses import dataclass
from typing import Any
from enum import Enum


from .client import ShowResponse, StatusResponse, ResponseError


class RESPONSESTATES(Enum):
    OK = ("ok",)
    ERROR = "error"


@dataclass
class ResponseState:
    state: RESPONSESTATES
    message: str
    response: ShowResponse | StatusResponse | ResponseError

    def __init__(
        self,
        state: RESPONSESTATES,
        message: str | None = None,
        response: ShowResponse | StatusResponse | ResponseError | None = None,
    ):
        self.state = state
        self.message = message or ""
        self.response = response

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "response": self.response,
        }


@dataclass
class ModuleSize:
    size: str
    installed: bool

    def to_dict(self) -> dict[str, Any]:
        return {"size": self.size, "installed": self.installed}
