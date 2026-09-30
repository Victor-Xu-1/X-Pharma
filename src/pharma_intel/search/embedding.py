from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from pharma_intel.config import Settings


class EmbeddingGatewayError(RuntimeError):
    """Raised when the governed embedding boundary returns an unusable result."""


class TextEmbedder(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAICompatibleEmbeddingGateway:
    def __init__(self, settings: Settings) -> None:
        try:
            settings.validate_remote_embedding_api(require_api_key=True)
        except RuntimeError as exc:
            raise EmbeddingGatewayError(str(exc)) from exc
        self.settings = settings
        self.endpoint = _embedding_endpoint(settings.search_embedding_base_url)

    @property
    def model(self) -> str:
        return self.settings.search_embedding_model

    @property
    def dimensions(self) -> int:
        return self.settings.search_embedding_dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        inputs = list(texts)
        if not inputs:
            return []
        if len(inputs) > self.settings.search_embedding_batch_size:
            raise EmbeddingGatewayError("Embedding batch exceeds the configured limit")
        if any(not text.strip() for text in inputs):
            raise EmbeddingGatewayError("Embedding input cannot be empty")
        if any(len(text) > self.settings.search_embedding_max_input_chars for text in inputs):
            raise EmbeddingGatewayError("Embedding input exceeds the configured character limit")
        response = self._request(
            {
                "model": self.model,
                "input": inputs,
                "encoding_format": "float",
            }
        )
        try:
            payload = response.json()
            rows = payload["data"]
            if not isinstance(rows, list) or len(rows) != len(inputs):
                raise ValueError("response row count does not match input count")
            ordered: list[list[float] | None] = [None] * len(inputs)
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("embedding row must be an object")
                index = row.get("index")
                vector = row.get("embedding")
                if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(inputs):
                    raise ValueError("embedding row index is invalid")
                if ordered[index] is not None:
                    raise ValueError("embedding row index is duplicated")
                ordered[index] = _validate_vector(vector, self.dimensions)
            if any(vector is None for vector in ordered):
                raise ValueError("embedding response omitted an input")
            return [vector for vector in ordered if vector is not None]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingGatewayError(f"Embedding response failed validation: {exc}") from exc

    def _request(self, payload: dict[str, object]) -> httpx.Response:
        last_error: Exception | None = None
        attempts = self.settings.search_embedding_max_retries + 1
        for attempt in range(attempts):
            try:
                response = httpx.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.settings.search_embedding_api_key}"},
                    json=payload,
                    timeout=self.settings.search_embedding_request_timeout_seconds,
                    trust_env=False,
                )
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    last_error = httpx.HTTPStatusError(
                        f"Retryable embedding response {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                else:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise EmbeddingGatewayError(
                            f"Embedding gateway rejected the request with status {response.status_code}"
                        ) from exc
                    return response
            except httpx.RequestError as exc:
                last_error = exc
            if attempt < attempts - 1:
                time.sleep(min(2**attempt, 8))
        raise EmbeddingGatewayError(f"Embedding request failed after {attempts} attempts: {last_error}")


def _embedding_endpoint(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise EmbeddingGatewayError("Embedding base URL must be a credential-free HTTPS remote API root")
    path = parsed.path.rstrip("/")
    path = f"{path}/embeddings" if path.endswith("/v1") else f"{path}/v1/embeddings"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _validate_vector(raw: object, dimensions: int) -> list[float]:
    if not isinstance(raw, list) or len(raw) != dimensions:
        raise ValueError(f"embedding vector must contain exactly {dimensions} values")
    vector: list[float] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("embedding vector contains a non-numeric value")
        resolved = float(value)
        if not math.isfinite(resolved):
            raise ValueError("embedding vector contains a non-finite value")
        vector.append(resolved)
    if not any(value != 0 for value in vector):
        raise ValueError("embedding vector cannot be the zero vector")
    return vector
