"""Read immutable migration identities from the candidate, without connecting to a database."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from scripts.release.contracts.core import LEGACY_DATABASE_ALEMBIC_HEAD

_SOURCE_ROOT = Path(__file__).resolve().parents[3]


def _migration_directory(root: Path) -> ScriptDirectory:
    directory = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    if len(directory.get_heads()) != 1:
        raise ValueError("candidate migration metadata must have exactly one head")
    return directory


def known_migration_revisions(root: Path) -> frozenset[str]:
    directory = _migration_directory(root)
    return frozenset(revision.revision for revision in directory.walk_revisions())


def current_migration_head(root: Path) -> str:
    directory = _migration_directory(root)
    # Force complete graph resolution: a dangling or cyclic ancestor is not valid authority.
    tuple(directory.walk_revisions())
    return directory.get_heads()[0]


def policy_migration_head(document: Mapping[str, object], path: Path) -> str:
    head = document.get("database_alembic_head", LEGACY_DATABASE_ALEMBIC_HEAD)
    if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{12}", head) is None:
        raise ValueError("release evidence policy has an invalid database migration head")
    if path == (_SOURCE_ROOT / "deploy/release/evidence-policy.json").resolve():
        try:
            expected = current_migration_head(_SOURCE_ROOT)
        except Exception as exc:  # Malformed Alembic graphs raise multiple exception families; fail closed.
            raise ValueError("candidate migration authority is unavailable") from exc
        if head != expected:
            raise ValueError("authoritative release policy does not match the candidate migration head")
    # Bundled policies are immutable snapshots, not requests to use today's source head.
    return head
