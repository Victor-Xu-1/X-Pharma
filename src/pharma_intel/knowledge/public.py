from __future__ import annotations

import re

_FRONT_MATTER_KEY = re.compile(r"^[A-Za-z_][\w-]*\s*:")


def public_knowledge_markdown(markdown: str) -> str:
    """Remove compiler-owned YAML front matter from a public knowledge document."""
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return markdown
    closing_delimiter = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        -1,
    )
    if closing_delimiter < 2 or not any(_FRONT_MATTER_KEY.match(line) for line in lines[1:closing_delimiter]):
        return markdown
    return "\n".join(lines[closing_delimiter + 1 :]).lstrip("\n")
