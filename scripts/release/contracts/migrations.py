"""Read immutable migration identities from the candidate, without connecting to a database."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def known_migration_revisions(root: Path) -> frozenset[str]:
    directory = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    if len(directory.get_heads()) != 1:
        raise ValueError("candidate migration metadata must have exactly one head")
    return frozenset(revision.revision for revision in directory.walk_revisions())
