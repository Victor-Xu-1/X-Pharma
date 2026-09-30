from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from pharma_intel.config import Settings
from pharma_intel.object_store import (
    FileSystemObjectStore,
    ObjectStoreError,
    S3ObjectStore,
    build_object_store,
)


def test_filesystem_object_store_is_immutable_and_checksum_verified(tmp_path: Path) -> None:
    store = FileSystemObjectStore(tmp_path / "objects")
    payload = b"source-backed evidence"
    digest = hashlib.sha256(payload).hexdigest()

    first = store.put_bytes("tenant-1", "parsed", payload, digest, ".txt")
    second = store.put_bytes("tenant-1", "parsed", payload, digest, ".txt")
    assert first == second
    assert store.read_bytes(first.uri, 1_000) == payload

    destination = tmp_path / "materialized" / "evidence.txt"
    store.materialize(first.uri, destination)
    assert destination.read_bytes() == payload

    source = tmp_path / "paper.pdf"
    source.write_bytes(payload)
    snapshot = store.put_file("tenant-1", "raw", source, digest)
    assert snapshot.size_bytes == len(payload)

    snapshot_path = Path(url2pathname(unquote(urlparse(snapshot.uri).path)))
    legacy_path = snapshot_path.relative_to(store.root)
    legacy_uri = (Path("/app/data/object-store") / legacy_path).as_uri()
    assert store.read_bytes(legacy_uri, 1_000) == payload

    with pytest.raises(ObjectStoreError, match="declared SHA-256"):
        store.put_bytes("tenant-1", "parsed", payload, "0" * 64, ".txt")
    with pytest.raises(ObjectStoreError, match="Invalid tenant"):
        store.put_bytes("../tenant", "parsed", payload, digest, ".txt")
    with pytest.raises(ObjectStoreError, match="read limit"):
        store.read_bytes(first.uri, 1)
    with pytest.raises(ObjectStoreError, match="file object URI"):
        store.read_bytes("https://example.test/evidence", 1_000)

    object_path = Path(url2pathname(unquote(urlparse(first.uri).path)))
    object_path.write_bytes(b"tampered")
    with pytest.raises(ObjectStoreError, match="checksum mismatch"):
        store.put_bytes("tenant-1", "parsed", payload, digest, ".txt")


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str]]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        item = self.objects.get((Bucket, Key))
        if item is None:
            raise ClientError({"Error": {"Code": "404", "Message": "missing"}}, "HeadObject")
        payload, metadata = item
        return {"ContentLength": len(payload), "Metadata": metadata}

    def upload_fileobj(
        self,
        stream: Any,
        bucket: str,
        key: str,
        ExtraArgs: dict[str, Any],  # noqa: N803
    ) -> None:
        self.objects[(bucket, key)] = (stream.read(), dict(ExtraArgs["Metadata"]))

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        payload, _ = self.objects[(Bucket, Key)]
        return {"ContentLength": len(payload), "Body": io.BytesIO(payload)}

    def download_file(self, bucket: str, key: str, destination: str) -> None:
        Path(destination).write_bytes(self.objects[(bucket, key)][0])

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop((Bucket, Key), None)


def test_s3_object_store_uses_content_addressing_and_bounded_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeS3Client()
    monkeypatch.setattr("pharma_intel.object_store.boto3.client", lambda *_args, **_kwargs: client)
    settings = Settings(
        object_store_backend="s3",
        object_store_s3_bucket="test-bucket",
        object_store_s3_access_key_id="access",
        object_store_s3_secret_access_key="secret",  # noqa: S106
    )
    store = build_object_store(settings)
    assert isinstance(store, S3ObjectStore)
    payload = b"immutable object"
    digest = hashlib.sha256(payload).hexdigest()

    stored = store.put_bytes("tenant-1", "raw", payload, digest, ".bin")
    assert stored.uri.startswith("s3://test-bucket/tenant-1/raw/")
    assert store.put_bytes("tenant-1", "raw", payload, digest, ".bin") == stored
    assert store.read_bytes(stored.uri, 100) == payload

    destination = tmp_path / "download" / "object.bin"
    store.materialize(stored.uri, destination)
    assert destination.read_bytes() == payload

    source = tmp_path / "source.txt"
    source.write_bytes(payload)
    assert store.put_file("tenant-1", "raw-file", source, digest).size_bytes == len(payload)

    with pytest.raises(ObjectStoreError, match="read limit"):
        store.read_bytes(stored.uri, 2)
    with pytest.raises(ObjectStoreError, match="unexpected bucket"):
        store.read_bytes(stored.uri.replace("test-bucket", "other-bucket"), 100)
    with pytest.raises(ObjectStoreError, match="Invalid S3"):
        store.materialize("s3://test-bucket", destination)

    assert store.delete(stored.uri, digest) is True
    assert store.delete(stored.uri, digest) is False
    with pytest.raises(ObjectStoreError, match="unexpected bucket"):
        store.delete(stored.uri.replace("test-bucket", "other-bucket"), digest)


def test_build_object_store_selects_filesystem(tmp_path: Path) -> None:
    store = build_object_store(Settings(object_store_root=tmp_path / "objects"))

    assert isinstance(store, FileSystemObjectStore)


def test_filesystem_delete_is_owned_verified_and_idempotent(tmp_path: Path) -> None:
    store = FileSystemObjectStore(tmp_path / "objects")
    payload = b"retention controlled artifact"
    digest = hashlib.sha256(payload).hexdigest()
    stored = store.put_bytes("tenant-1", "exports-job", payload, digest, ".jsonl")

    with pytest.raises(ObjectStoreError, match="checksum mismatch"):
        store.delete(stored.uri, "0" * 64)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(payload)
    with pytest.raises(ObjectStoreError, match="configured root"):
        store.delete(outside.resolve().as_uri(), digest)

    assert store.delete(stored.uri, digest) is True
    assert store.delete(stored.uri, digest) is False
