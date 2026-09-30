from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_EXPORT_BYTES = 256 * 1024 * 1024
MAX_QUERIES = 100
MAX_QUERY_CHARS = 2_000


class RagflowMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationDataset:
    key: str
    external_id: str


class ReadOnlyRagflowMigrationClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 60) -> None:
        self.base_url = _validated_base_url(base_url)
        if not api_key.strip():
            raise RagflowMigrationError("RAGFlow migration API key is not configured")
        if not 1 <= timeout <= 300:
            raise RagflowMigrationError("RAGFlow migration timeout must be between 1 and 300 seconds")
        self.api_key = api_key
        self.timeout = timeout

    def retrieve(self, query: str, dataset_ids: list[str], limit: int) -> list[dict[str, Any]]:
        response = self._request_json(
            "/api/v1/retrieval",
            {"question": query, "dataset_ids": dataset_ids, "page_size": limit},
        )
        chunks = (response.get("data") or {}).get("chunks") or []
        if not isinstance(chunks, list):
            raise RagflowMigrationError("RAGFlow migration response has an invalid chunk list")
        if len(chunks) > limit:
            raise RagflowMigrationError("RAGFlow migration response exceeds the requested chunk limit")
        if not all(isinstance(item, dict) for item in chunks):
            raise RagflowMigrationError("RAGFlow migration response contains an invalid chunk")
        return chunks

    def _request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}{path}",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise RagflowMigrationError("RAGFlow migration response exceeds the size limit")
        except httpx.HTTPError as exc:
            raise RagflowMigrationError(f"RAGFlow migration request failed: {exc}") from exc
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RagflowMigrationError("RAGFlow migration response is not valid JSON") from exc
        if not isinstance(document, dict) or document.get("code", 0) != 0:
            raise RagflowMigrationError("RAGFlow migration request was rejected")
        return document


def export_queries(
    client: ReadOnlyRagflowMigrationClient,
    datasets: list[MigrationDataset],
    queries: list[str],
    *,
    limit: int,
    output: Path,
) -> dict[str, Any]:
    if not datasets or len({item.key for item in datasets}) != len(datasets):
        raise RagflowMigrationError("Migration datasets must contain unique logical keys")
    if not 1 <= limit <= 100:
        raise RagflowMigrationError("Migration query limit must be between 1 and 100")
    normalized_queries = [query.strip() for query in queries if query.strip()]
    if not normalized_queries or len(normalized_queries) > MAX_QUERIES:
        raise RagflowMigrationError(f"Migration query count must be between 1 and {MAX_QUERIES}")
    if any(len(query) > MAX_QUERY_CHARS for query in normalized_queries):
        raise RagflowMigrationError(f"Migration queries cannot exceed {MAX_QUERY_CHARS} characters")
    dataset_by_id = {item.external_id: item.key for item in datasets}
    if len(dataset_by_id) != len(datasets):
        raise RagflowMigrationError("Migration external dataset IDs must be unique")

    records: list[dict[str, Any]] = []
    estimated_record_bytes = 0
    for query in normalized_queries:
        chunks = client.retrieve(query, list(dataset_by_id), limit)
        for chunk in chunks:
            external_id = str(chunk.get("dataset_id", ""))
            dataset_key = dataset_by_id.get(external_id)
            if dataset_key is None:
                raise RagflowMigrationError("RAGFlow returned a chunk outside the approved migration datasets")
            record = {
                "query": query,
                "dataset_key": dataset_key,
                "document_id": str(chunk.get("document_id", "")),
                "document_name": str(chunk.get("document_name", "")),
                "content": str(chunk.get("content", "")),
                "similarity": chunk.get("similarity"),
                "positions": chunk.get("positions") or [],
                "metadata": chunk.get("document_metadata") or {},
            }
            estimated_record_bytes += len(json.dumps(record, ensure_ascii=True).encode())
            if estimated_record_bytes > MAX_EXPORT_BYTES:
                raise RagflowMigrationError("RAGFlow migration export exceeds the size limit")
            records.append(record)
    document = {
        "schema": "pharma.ragflow-offline-export.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_base_url": client.base_url,
        "datasets": [
            {"key": item.key, "external_id_sha256": hashlib.sha256(item.external_id.encode()).hexdigest()}
            for item in datasets
        ],
        "queries": normalized_queries,
        "record_count": len(records),
        "records": records,
    }
    rendered = (json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
    if len(rendered) > MAX_EXPORT_BYTES:
        raise RagflowMigrationError("RAGFlow migration export exceeds the size limit")
    _write_exclusive(output, rendered)
    return document


def _validated_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RagflowMigrationError("RAGFlow migration base URL is invalid")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RagflowMigrationError("RAGFlow migration base URL cannot contain credentials, query or fragment")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RagflowMigrationError("RAGFlow migration requires HTTPS except for loopback endpoints")
    return value.strip().rstrip("/")


def _write_exclusive(path: Path, content: bytes) -> None:
    if path.is_symlink():
        raise RagflowMigrationError(f"Migration export cannot be a symbolic link: {path}")
    parent = path.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / path.name
    if path.exists() or path.is_symlink():
        raise RagflowMigrationError(f"Migration export already exists: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.chmod(0o600)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise RagflowMigrationError(f"Migration export already exists: {path}") from exc
        directory_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _parse_dataset(value: str) -> MigrationDataset:
    key, separator, external_id = value.partition("=")
    if not separator or not key.strip() or not external_id.strip():
        raise argparse.ArgumentTypeError("dataset must use KEY=RAGFLOW_ID")
    return MigrationDataset(key.strip(), external_id.strip())


def run() -> None:
    parser = argparse.ArgumentParser(description="Export approved RAGFlow retrieval results for offline migration")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="RAGFLOW_MIGRATION_API_KEY")
    parser.add_argument("--dataset", action="append", required=True, type=_parse_dataset)
    parser.add_argument("--query-file", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    api_key = os.getenv(args.api_key_env, "")
    try:
        queries = json.loads(args.query_file.read_text(encoding="utf-8"))
        if not isinstance(queries, list) or not all(isinstance(item, str) for item in queries):
            raise RagflowMigrationError("Migration query file must contain a JSON string array")
        client = ReadOnlyRagflowMigrationClient(args.base_url, api_key, timeout=args.timeout)
        export_queries(client, args.dataset, queries, limit=args.limit, output=args.output)
    except (OSError, json.JSONDecodeError, RagflowMigrationError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    run()
