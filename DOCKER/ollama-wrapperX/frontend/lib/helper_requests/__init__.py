import requests

from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "helper_requests"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(url: str, params: dict | None) -> str:
    param_string = urlencode(sorted(params.items())) if params else ""
    key_source = f"{url}?{param_string}"
    return sha256(key_source.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.html"


def get_html(url, params=None, timeout=15) -> str:
    cache_key = _cache_key(url, params)
    cache_file = _cache_path(cache_key)

    if cache_file.exists():
        return cache_file.read_text()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }
    )

    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    cache_file.write_text(resp.text)
    return resp.text
