from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from lib.helper_ollama.types import ModuleSize
from lib.helper_requests import get_html

COUNT_RE = re.compile(r"(\d+)")


def _clean_text(node: Optional[Tag]) -> str:
    if not node:
        return ""
    return node.get_text(" ", strip=True)


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = COUNT_RE.search(value.replace(",", ""))
    if not match:
        return None
    return int(match.group(1))


def _collect_categories(item: Tag) -> List[str]:
    seen: set[str] = set()
    categories: List[str] = []
    for span in item.find_all(attrs={"x-test-capability": True}):
        text = _clean_text(span)
        normalized = text.strip()
        if normalized and normalized.lower() not in seen:
            categories.append(normalized)
            seen.add(normalized.lower())
    for span in item.select('span[class*="bg-cyan"]'):
        if span.has_attr("x-test-size"):
            continue
        text = _clean_text(span)
        normalized = text.strip()
        if normalized and normalized.lower() not in seen:
            categories.append(normalized)
            seen.add(normalized.lower())
    return categories


def _collect_sizes(item: Tag) -> List[ModuleSize]:
    sizes: List[ModuleSize] = []

    for span in item.find_all(attrs={"x-test-size": True}):
        text = _clean_text(span)
        if text:
            size = ModuleSize(size=text.strip(), installed=True)
            sizes.append(size)

    return sizes


def scrape_library(
    helper: "Helper", # type: ignore  # noqa: F821
    content: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if content is not None:
        resp_text = content
    else:
        resp_text = get_html("https://ollama.com/library", timeout=15)

    soup = BeautifulSoup(resp_text, "html.parser")
    items = soup.find_all(attrs={"x-test-model": True})

    payloads: List[Dict[str, Any]] = []

    for item in items:
        anchor = item.find("a", href=True)
        if not anchor:
            continue
        href_value = anchor.get("href")
        if not href_value:
            continue
        href = str(href_value)
        slug = href.split("/")[-1].strip()

        title_block = anchor.find(attrs={"x-test-model-title": True})
        if not title_block:
            continue

        title_value = title_block.get("title")
        if title_value:
            name = str(title_value).strip()
        else:
            name = _clean_text(title_block)

        if not name:
            continue

        description = _clean_text(title_block.find("p"))
        categories = _collect_categories(item)

        sizes = _collect_sizes(item)

        pull_tag = item.select_one("[x-test-pull-count]")
        pulls = _parse_int(_clean_text(pull_tag))
        tag_tag = item.select_one("[x-test-tag-count]")
        tag_count = _parse_int(_clean_text(tag_tag))
        updated_tag = item.select_one("[x-test-updated]")
        updated = _clean_text(updated_tag)
        updated_timestamp = updated_tag.get("title") if updated_tag else None
        extras: Dict[str, Any] = {}

        if pulls is not None:
            extras["pulls"] = pulls

        if updated_timestamp:
            extras["updated_timestamp"] = updated_timestamp

        payloads.append(
            {
                "name": name,
                "slug": slug,
                "url": f"https://ollama.com{href}",
                "description": description,
                "categories": categories,
                "sizes": sizes,
                "tags_count": tag_count,
                "updated": updated,
                "extras": extras,
            }
        )

    return payloads
