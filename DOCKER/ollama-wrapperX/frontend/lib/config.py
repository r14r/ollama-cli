import os

OLLAMA_URL_PUBLIC  = os.getenv("OLLAMA_URL_PUBLIC", None)
GATEWAY_URL_PUBLIC = os.getenv("GATEWAY_URL_PUBLIC", None)

if OLLAMA_URL_PUBLIC is None:
    raise RuntimeError("Missing environment variable OLLAMA_URL_PUBLIC")

if GATEWAY_URL_PUBLIC is None:
    raise RuntimeError("Missing environment variable GATEWAY_URL_PUBLIC")


def get_gateway_url():
    return GATEWAY_URL_PUBLIC


def get_ollama_url():
    return OLLAMA_URL_PUBLIC
