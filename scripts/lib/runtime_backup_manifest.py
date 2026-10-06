from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"invalid backup {label}")
    return value


def restore_database_records(document: Mapping[str, object]) -> list[tuple[str, ...]]:
    """Return validated argv identities, never SQL or credentials from a manifest."""
    if type(document.get("schemaVersion")) is not int or document["schemaVersion"] != 1:
        raise ValueError("unsupported backup schemaVersion")
    database = _identifier(document.get("database"), "database")
    if database in {"postgres", "template0", "template1", "bootstrap", "temporal", "temporal_visibility"}:
        raise ValueError("business database overlaps a reserved restore database")
    names = [database, "temporal", "temporal_visibility"]
    owners = document.get("databaseOwners")
    admin = document.get("postgresAdminUser")
    if owners is None and admin is None and database == "pharma_intel":
        # The original v1 producer supported this one documented identity only.
        owners = dict.fromkeys(names, "pharma_app")
        admin = "pharma_app"
    if not isinstance(owners, dict) or set(owners) != set(names):
        raise ValueError("backup must declare the exact three database owners; recreate a nondefault legacy backup")
    administrator = _identifier(admin, "administrator")
    records: list[tuple[str, ...]] = [(database, administrator)]
    dumps = ["postgres.dump", "temporal.dump", "temporal-visibility.dump"]
    for name, dump in zip(names, dumps, strict=True):
        records.append((name, _identifier(owners[name], "database owner"), dump))
    return records


def main() -> int:
    if len(sys.argv) != 2:
        raise ValueError("usage: runtime_backup_manifest.py MANIFEST")
    document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError("backup manifest must be an object")
    for record in restore_database_records(document):
        print("\t".join(record))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
