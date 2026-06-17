import json
from typing import Any, Dict, List, Optional

import requests


class GatewayClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get(self, path: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    def chat(self,
             model: str,
             messages: List[Dict[str, str]],
             target: str = "gateway",
             stream: bool = False) -> Dict[str, Any]:
        payload = {"model": model, "messages": messages, "target": target, "stream": stream}
        return self._post("/chat", payload)

    def prompt_templates(self) -> List[Dict[str, Any]]:
        return self._get("/prompts/list")

    def create_template(self, name: str, description: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return self._post("/prompts", {"name": name, "description": description, "messages": messages})

    def delete_template(self, template_id: int) -> Dict[str, Any]:
        response = requests.delete(f"{self.base_url}/prompts/{template_id}", timeout=30)
        response.raise_for_status()
        return response.json()

    def metrics(self) -> str:
        response = requests.get(f"{self.base_url}/metrics", timeout=30)
        response.raise_for_status()
        return response.text


def load_template_from_file(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
