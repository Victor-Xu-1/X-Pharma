from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PARSER_PROTOCOL_VERSION = 2
SUPPORTED_DOCUMENT_SUFFIXES = frozenset(
    {
        ".cif",
        ".csv",
        ".docx",
        ".htm",
        ".html",
        ".jpeg",
        ".jpg",
        ".json",
        ".md",
        ".mmcif",
        ".mol",
        ".nxml",
        ".pdb",
        ".pdf",
        ".png",
        ".pptx",
        ".sdf",
        ".txt",
        ".tif",
        ".tiff",
        ".xml",
        ".xlsx",
    }
)


class ParserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(default=PARSER_PROTOCOL_VERSION, ge=1, le=PARSER_PROTOCOL_VERSION)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any]
    parser_name: str = Field(min_length=1, max_length=120)
    parser_version: str = Field(min_length=1, max_length=120)


class ParserProcessEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(default=PARSER_PROTOCOL_VERSION, ge=1, le=PARSER_PROTOCOL_VERSION)
    status: str = Field(pattern=r"^(succeeded|rejected|failed)$")
    result: ParserResponse | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    error_message: str | None = Field(default=None, max_length=1000)
