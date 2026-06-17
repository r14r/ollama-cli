from typing import Any, Dict, List, Optional

from requests import request, Response
from requests.exceptions import ChunkedEncodingError

from lib.config import get_gateway_url
from lib.gateway import gateway_call

def admin_call(
    path: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    stream: bool = False,
) -> Response:
    url = f"{get_gateway_url()}{path}"
    response = request(method, url, json=payload, timeout=60, stream=stream)
    response.raise_for_status()
    return response


def safe_json(response: Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def load_prompt_templates() -> List[Dict[str, Any]]:
    try:
        return gateway_call("/extended/prompts").json()
    except Exception:
        return []


def fetch_models() -> List[Dict[str, Any]]:
    try:
        response = gateway_call("/extended/models")
        return response.json().get("models") or response.json().get("models", [])
    except Exception:
        return []


def stream_response(response: Response, buffer):
    accumulated = ""
    try:
        for line in response.iter_lines(decode_unicode=True):
            if line:
                accumulated += line + "\n"
                buffer.text(accumulated)
    except ChunkedEncodingError:
        buffer.text(accumulated + "\nStream ended (ChunkedEncodingError).")
    else:
        buffer.text(accumulated + "\nFinished.")
