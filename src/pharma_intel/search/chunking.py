from __future__ import annotations

import re
from dataclasses import dataclass

LOCATOR_PATTERN = re.compile(r"^\[\[(page|slide|sheet|table):([^\]]+)\]\]\s*$")


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    content: str
    start_char: int
    end_char: int
    locator_kind: str | None
    locator_value: str | None


def chunk_text(text: str, max_chars: int, overlap_chars: int) -> list[TextChunk]:
    if max_chars <= 0 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Chunk size must be positive and overlap must be smaller than the chunk")
    sections = _sections(text)
    chunks: list[TextChunk] = []
    for start, end, locator_kind, locator_value in sections:
        cursor = start
        while cursor < end:
            hard_end = min(cursor + max_chars, end)
            cut = hard_end
            if hard_end < end:
                preferred = text.rfind("\n", cursor + max_chars // 2, hard_end)
                if preferred > cursor:
                    cut = preferred
            raw = text[cursor:cut]
            content = raw.strip()
            if content:
                leading = len(raw) - len(raw.lstrip())
                trailing = len(raw.rstrip())
                chunks.append(
                    TextChunk(
                        ordinal=len(chunks),
                        content=content,
                        start_char=cursor + leading,
                        end_char=cursor + trailing,
                        locator_kind=locator_kind,
                        locator_value=locator_value,
                    )
                )
            if cut >= end:
                break
            cursor = max(cut - overlap_chars, cursor + 1)
    return chunks


def _sections(text: str) -> list[tuple[int, int, str | None, str | None]]:
    sections: list[tuple[int, int, str | None, str | None]] = []
    content_start = 0
    locator_kind: str | None = None
    locator_value: str | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        match = LOCATOR_PATTERN.fullmatch(line.strip())
        if match:
            if content_start < offset and text[content_start:offset].strip():
                sections.append((content_start, offset, locator_kind, locator_value))
            locator_kind, locator_value = match.groups()
            content_start = offset + len(line)
        offset += len(line)
    if content_start < len(text) and text[content_start:].strip():
        sections.append((content_start, len(text), locator_kind, locator_value))
    if not sections and text.strip():
        sections.append((0, len(text), None, None))
    return sections
