from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from pharma_intel.config import Settings

SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class ObjectStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    uri: str
    content_sha256: str
    size_bytes: int


class ObjectStore(Protocol):
    def put_file(self, tenant_id: str, category: str, path: Path, content_sha256: str) -> StoredObject: ...

    def put_bytes(
        self,
        tenant_id: str,
        category: str,
        data: bytes,
        content_sha256: str,
        suffix: str,
    ) -> StoredObject: ...

    def materialize(self, uri: str, destination: Path) -> None: ...

    def read_bytes(self, uri: str, max_bytes: int) -> bytes: ...

    def delete(self, uri: str, expected_sha256: str) -> bool: ...


def _validate_segment(value: str, label: str) -> str:
    if not SAFE_SEGMENT.fullmatch(value):
        raise ObjectStoreError(f"Invalid {label} segment")
    return value


def _object_key(tenant_id: str, category: str, content_sha256: str, suffix: str) -> str:
    _validate_segment(tenant_id, "tenant")
    _validate_segment(category, "category")
    if not re.fullmatch(r"[a-f0-9]{64}", content_sha256):
        raise ObjectStoreError("Invalid SHA-256 digest")
    safe_suffix = suffix.casefold() if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix.casefold()) else ""
    return f"{tenant_id}/{category}/{content_sha256[:2]}/{content_sha256}{safe_suffix}"


class FileSystemObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.temporary_root = self.root / ".tmp"
        self.temporary_root.mkdir(parents=True, exist_ok=True)

    def _target(self, key: str) -> Path:
        target = (self.root / Path(*key.split("/"))).resolve()
        if not target.is_relative_to(self.root):
            raise ObjectStoreError("Object key escaped the configured root")
        return target

    def put_file(self, tenant_id: str, category: str, path: Path, content_sha256: str) -> StoredObject:
        key = _object_key(tenant_id, category, content_sha256, path.suffix)
        target = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return self._verify_existing(target, content_sha256)
        temporary = self.temporary_root / f"{uuid.uuid4().hex}.tmp"
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as source, temporary.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            if digest.hexdigest() != content_sha256:
                raise ObjectStoreError("Source changed while its immutable snapshot was being created")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return StoredObject(target.as_uri(), content_sha256, size)

    def put_bytes(
        self,
        tenant_id: str,
        category: str,
        data: bytes,
        content_sha256: str,
        suffix: str,
    ) -> StoredObject:
        if hashlib.sha256(data).hexdigest() != content_sha256:
            raise ObjectStoreError("Byte payload does not match its declared SHA-256 digest")
        key = _object_key(tenant_id, category, content_sha256, suffix)
        target = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return self._verify_existing(target, content_sha256)
        temporary = self.temporary_root / f"{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as destination:
                destination.write(data)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return StoredObject(target.as_uri(), content_sha256, len(data))

    def _verify_existing(self, target: Path, expected_sha256: str) -> StoredObject:
        digest, size = _hash_stream(target.open("rb"))
        if digest != expected_sha256:
            raise ObjectStoreError(f"Immutable object checksum mismatch: {target}")
        return StoredObject(target.as_uri(), digest, size)

    def materialize(self, uri: str, destination: Path) -> None:
        source = self._owned_path(uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    def read_bytes(self, uri: str, max_bytes: int) -> bytes:
        path = self._owned_path(uri)
        if path.stat().st_size > max_bytes:
            raise ObjectStoreError("Object exceeds the configured read limit")
        return path.read_bytes()

    def delete(self, uri: str, expected_sha256: str) -> bool:
        path = self._owned_path(uri)
        if not path.exists():
            return False
        digest, _ = _hash_stream(path.open("rb"))
        if digest != expected_sha256:
            raise ObjectStoreError("Object checksum mismatch; refusing deletion")
        path.unlink()
        return True

    def _owned_path(self, uri: str) -> Path:
        path = _file_uri_to_path(uri).resolve()
        if path.is_relative_to(self.root):
            owned_path = path
        else:
            legacy_root = Path("/app/data/object-store").resolve()
            if not path.is_relative_to(legacy_root):
                raise ObjectStoreError("Object URI escaped the configured root")
            owned_path = (self.root / path.relative_to(legacy_root)).resolve()
        if not owned_path.is_relative_to(self.root) or owned_path.is_relative_to(self.temporary_root):
            raise ObjectStoreError("Object URI escaped the configured root")
        return owned_path


class S3ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.object_store_s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_store_s3_endpoint_url or None,
            region_name=settings.object_store_s3_region,
            aws_access_key_id=settings.object_store_s3_access_key_id,
            aws_secret_access_key=settings.object_store_s3_secret_access_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
        )

    def put_file(self, tenant_id: str, category: str, path: Path, content_sha256: str) -> StoredObject:
        key = _object_key(tenant_id, category, content_sha256, path.suffix)
        existing = self._head(key, content_sha256)
        if existing is not None:
            return existing
        before = path.stat()
        with path.open("rb") as source:
            self._put_stream(key, source, content_sha256)
        after = path.stat()
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise ObjectStoreError("Source changed while its immutable snapshot was being uploaded")
        digest, size = _hash_stream(path.open("rb"))
        if digest != content_sha256:
            raise ObjectStoreError("Source checksum changed while its immutable snapshot was being uploaded")
        return StoredObject(f"s3://{self.bucket}/{key}", digest, size)

    def put_bytes(
        self,
        tenant_id: str,
        category: str,
        data: bytes,
        content_sha256: str,
        suffix: str,
    ) -> StoredObject:
        if hashlib.sha256(data).hexdigest() != content_sha256:
            raise ObjectStoreError("Byte payload does not match its declared SHA-256 digest")
        key = _object_key(tenant_id, category, content_sha256, suffix)
        existing = self._head(key, content_sha256)
        if existing is None:
            self._put_stream(key, io.BytesIO(data), content_sha256)
        return StoredObject(f"s3://{self.bucket}/{key}", content_sha256, len(data))

    def _put_stream(self, key: str, stream: BinaryIO, content_sha256: str) -> None:
        self.client.upload_fileobj(
            stream,
            self.bucket,
            key,
            ExtraArgs={"Metadata": {"content-sha256": content_sha256}, "ServerSideEncryption": "AES256"},
        )

    def _head(self, key: str, expected_sha256: str) -> StoredObject | None:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise ObjectStoreError(f"Object-store lookup failed: {exc}") from exc
        metadata = response.get("Metadata") or {}
        if metadata.get("content-sha256") != expected_sha256:
            raise ObjectStoreError("Immutable S3 object metadata checksum mismatch")
        return StoredObject(
            f"s3://{self.bucket}/{key}",
            expected_sha256,
            int(response.get("ContentLength", 0)),
        )

    def materialize(self, uri: str, destination: Path) -> None:
        bucket, key = _parse_s3_uri(uri)
        if bucket != self.bucket:
            raise ObjectStoreError("Object URI references an unexpected bucket")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(bucket, key, str(destination))

    def read_bytes(self, uri: str, max_bytes: int) -> bytes:
        bucket, key = _parse_s3_uri(uri)
        if bucket != self.bucket:
            raise ObjectStoreError("Object URI references an unexpected bucket")
        response = self.client.get_object(Bucket=bucket, Key=key)
        if int(response.get("ContentLength", 0)) > max_bytes:
            response["Body"].close()
            raise ObjectStoreError("Object exceeds the configured read limit")
        try:
            return bytes(response["Body"].read(max_bytes + 1))
        finally:
            response["Body"].close()

    def delete(self, uri: str, expected_sha256: str) -> bool:
        bucket, key = _parse_s3_uri(uri)
        if bucket != self.bucket:
            raise ObjectStoreError("Object URI references an unexpected bucket")
        existing = self._head(key, expected_sha256)
        if existing is None:
            return False
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            raise ObjectStoreError(f"Object-store deletion failed: {exc}") from exc
        return True


def _hash_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    finally:
        stream.close()
    return digest.hexdigest(), size


def _file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ObjectStoreError("Expected a file object URI")
    path = url2pathname(unquote(parsed.path))
    if parsed.netloc:
        path = f"//{parsed.netloc}{path}"
    return Path(path)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ObjectStoreError("Invalid S3 object URI")
    return parsed.netloc, parsed.path.lstrip("/")


def build_object_store(settings: Settings) -> ObjectStore:
    if settings.object_store_backend == "s3":
        return S3ObjectStore(settings)
    return FileSystemObjectStore(settings.object_store_root)
