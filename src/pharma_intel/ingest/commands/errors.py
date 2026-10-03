from typing import Any


class IngestionCommandError(RuntimeError):
    def __init__(self, status_code: int, detail: str | dict[str, Any]) -> None:
        super().__init__(detail if isinstance(detail, str) else str(detail.get("code", "Ingestion command failed")))
        self.status_code = status_code
        self.detail = detail
