from typing import Any, Dict, Optional

from requests import request, Response

from lib.config import get_gateway_url
from lib.response import ErrorResponse



def gateway_call(path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Response:
    url = f"{get_gateway_url()}{path}"

    response = None

    try:
        response = request(method, url, json=payload, timeout=60)
        response.raise_for_status()

        response = response.json()
    except Exception as e:
        response = ErrorResponse(url, e)

    return response
