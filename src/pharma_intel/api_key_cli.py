from __future__ import annotations

import argparse
import json
import os
import stat
import uuid
from pathlib import Path

from sqlalchemy import select

from pharma_intel.api_key_lifecycle import ApiKeyLifecycleError, ApiKeyLifecycleService
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import Tenant


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate tenant API-key lifecycle")
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--actor", required=True, help="Named operator or change-ticket identity")
    commands = parser.add_subparsers(dest="command", required=True)
    rotate = commands.add_parser("rotate")
    rotate.add_argument("--key-id", required=True)
    rotate.add_argument("--new-name")
    rotate.add_argument("--secret-output", required=True, type=Path)
    return parser


def _resolve_secret_output(path: Path) -> Path:
    if not path.is_absolute():
        raise ApiKeyLifecycleError("--secret-output must be an absolute path")
    parent = path.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ApiKeyLifecycleError("secret output parent must be a directory")
    mode = stat.S_IMODE(parent.stat().st_mode)
    if os.name != "nt" and mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ApiKeyLifecycleError("secret output parent must not be group/world writable")
    resolved = parent / path.name
    if resolved.exists():
        raise ApiKeyLifecycleError("refusing to overwrite an existing secret output")
    return resolved


def _write_secret(path: Path, secret: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(secret)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        if os.name != "nt":
            directory_flag = getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(path.parent, os.O_RDONLY | directory_flag)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except BaseException as exc:
        _unlink_without_masking(temporary, exc)
        raise


def _unlink_without_masking(path: Path, primary_error: BaseException) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        primary_error.add_note(f"Could not remove partial secret artifact {path}: {cleanup_error}")


def run() -> None:
    parser = _parser()
    args = parser.parse_args()
    secret_output: Path | None = None
    try:
        if args.command != "rotate":
            parser.error("unsupported API-key lifecycle command")
        secret_output = _resolve_secret_output(args.secret_output)
        with get_session_factory()() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
            if tenant is None:
                raise ApiKeyLifecycleError("tenant does not exist")
            set_tenant_context(session, tenant.id)
            rotation = ApiKeyLifecycleService(session, tenant, actor_id=args.actor).rotate(
                args.key_id,
                new_name=args.new_name,
            )
            try:
                _write_secret(secret_output, rotation.secret)
                session.commit()
            except BaseException as exc:
                session.rollback()
                _unlink_without_masking(secret_output, exc)
                secret_output = None
                raise
        print(
            json.dumps(
                {
                    "old_key_id": rotation.old_key_id,
                    "new_key_id": rotation.new_key_id,
                    "name": rotation.name,
                    "prefix": rotation.prefix,
                    "commercial_client_id": rotation.commercial_client_id,
                    "secret_output": str(secret_output),
                },
                sort_keys=True,
            )
        )
    except (ApiKeyLifecycleError, OSError) as exc:
        if secret_output is not None:
            _unlink_without_masking(secret_output, exc)
        parser.error(str(exc))


if __name__ == "__main__":
    run()
