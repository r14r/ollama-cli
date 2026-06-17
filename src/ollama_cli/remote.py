#!/usr/bin/env python3
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from . import utils


# ============================================================
#  Remote library operations
# ============================================================
def extract_models(
    html: str,
    *,
    limit: int,
    with_description: bool,
    filter_capabilities: list[str] | None = None,
    sort_by: str = "order",
) -> None:
    """Extract and display models from Ollama library HTML."""
    soup = BeautifulSoup(html, "html.parser")

    columns = ["model_name", "capabilities", "sizes", "updated"]
    if with_description:
        columns.append("description")

    rows: list[dict[str, Any]] = []
    normalized_filter_capabilities = {
        item.strip().lower() for item in (filter_capabilities or []) if item.strip()
    }

    order = 1

    for li in soup.find_all("li", attrs={"x-test-model": True}):
        if not isinstance(li, Tag):
            continue

        name_div = li.find("div", attrs={"title": True})
        model_name = (
            name_div.get("title", "").strip() if isinstance(name_div, Tag) else "N/A"
        )

        desc_p = li.find("p", class_="max-w-lg")
        description = desc_p.get_text(strip=True) if isinstance(desc_p, Tag) else ""

        capabilities: list[str] = []
        container = li.find("div", class_="flex flex-wrap space-x-2")
        if isinstance(container, Tag):
            for span in container.find_all(
                "span", class_="inline-flex", recursive=False
            ):
                if not isinstance(span, Tag):
                    continue
                if span.has_attr("x-test-size"):
                    continue
                text = span.get_text(strip=True)
                if text:
                    capabilities.append(text)

        sizes = [
            span.get_text(strip=True)
            for span in li.find_all("span", attrs={"x-test-size": True})
            if isinstance(span, Tag)
        ]

        update_span = li.find("span", attrs={"x-test-updated": True})
        updated = (
            update_span.get_text(strip=True) if isinstance(update_span, Tag) else "N/A"
        )

        capability_set = {cap.lower() for cap in capabilities}
        if normalized_filter_capabilities and not capability_set.intersection(
            normalized_filter_capabilities
        ):
            continue

        rows.append(
            {
                "order": order,
                "model_name": model_name,
                "capabilities": capabilities,
                "sizes": sizes,
                "updated": updated,
                "description": description,
            }
        )
        order += 1

    if not rows:
        print("No remote models found.")
        return

    def get_row_order(row: dict[str, Any], fallback: int) -> int:
        value = row.get("order")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return fallback

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[object, ...]:
        fallback_index, row = item
        model_name = str(row.get("model_name", "")).lower()
        capabilities = [str(x).lower() for x in row.get("capabilities", [])]
        sizes = [str(x).lower() for x in row.get("sizes", [])]
        updated = str(row.get("updated", "")).lower()
        order_value = get_row_order(row, fallback_index)

        if sort_by == "capability":
            return (",".join(capabilities), model_name, order_value)

        if sort_by == "size":
            return (len(sizes), ",".join(sizes), model_name, order_value)

        if sort_by == "date":
            return (updated, model_name, order_value)

        if sort_by == "name":
            return (model_name, order_value)

        return (order_value,)

    limited_rows = rows[:limit] if limit > 0 else rows

    limited_rows = [
        row for _, row in sorted(enumerate(limited_rows, start=1), key=sort_key)
    ]

    printable_rows: list[list[str]] = []
    for row in limited_rows:
        printable_row = [
            str(row["model_name"]),
            ", ".join(row["capabilities"]),
            ", ".join(row["sizes"]),
            str(row["updated"]),
        ]
        if with_description:
            printable_row.append(str(row["description"]))
        printable_rows.append(printable_row)

    col_count = len(columns)
    col_widths = [
        max(len(columns[i]), *(len(str(row[i])) for row in printable_rows))
        for i in range(col_count)
    ]

    if with_description:
        header = "  ".join(
            str(item).ljust(col_widths[i]) for i, item in enumerate(columns[:-1])
        )
        print(header)
        print()
        for row in printable_rows:
            print(
                "  ".join(
                    str(item).ljust(col_widths[i]) for i, item in enumerate(row[:-1])
                )
            )
            print(row[-1])
            print()
    else:
        print(
            "  ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(columns))
        )
        for row in printable_rows:
            print(
                "  ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(row))
            )


def cmd_list_remote_models(args: Any) -> None:
    """Fetch and display models from Ollama library website."""
    response = requests.get("https://ollama.com/library", timeout=20)
    response.raise_for_status()
    extract_models(
        response.text,
        limit=args.limit,
        with_description=args.with_description,
        filter_capabilities=args.filter_capabilities,
        sort_by=args.sort_by,
    )
