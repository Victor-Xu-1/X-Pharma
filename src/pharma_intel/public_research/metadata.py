from __future__ import annotations

import re
from typing import Any


def rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Public provider response is missing {key}")
    return value


def text(value: object, *, required: bool = False, limit: int = 600) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str | int | float) or isinstance(value, bool):
        raise ValueError("Invalid public metadata text")
    result = str(value).strip()
    if (
        (required and not result)
        or len(result) > limit
        or any(ord(char) < 32 and char not in "\t\n\r" for char in result)
    ):
        raise ValueError("Public metadata text is missing or exceeds the safety limit")
    return result


def identifier(value: object, pattern: str) -> str:
    result = text(value, required=True, limit=160)
    if re.fullmatch(pattern, result) is None:
        raise ValueError("Invalid public record identifier")
    return result


def total(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Invalid public result count")
    return value


def literal_query(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
