"""Deterministic search-only projection for admitted financial tables."""

from __future__ import annotations

from typing import Any

TABLE_SEARCH_PROJECTION_VERSION = "1.0"


def _display_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def build_table_search_text(table: dict[str, Any]) -> str:
    """Build ordered searchable display text without assigning table semantics."""

    values: list[str] = []
    for value in (table.get("caption"), (table.get("preceding_heading") or {}).get("text")):
        if isinstance(value, str) and value.strip():
            values.append(value)
    values.extend(_display_values(table.get("period_header_text")))
    values.extend(_display_values(table.get("unit_hints")))
    for row in table.get("rows", []):
        if not isinstance(row, dict):
            continue
        for cell in row.get("cells", []):
            if (
                isinstance(cell, dict)
                and isinstance(cell.get("text"), str)
                and cell["text"].strip()
            ):
                values.append(cell["text"])
    return " ".join(" ".join(values).split())
