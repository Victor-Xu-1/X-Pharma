from __future__ import annotations

import pytest

from scripts.lib.runtime_backup_manifest import restore_database_records


def test_restores_explicit_database_owners_without_a_default_role_assumption() -> None:
    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "database": "pharma_intel",
        "postgresAdminUser": "pharma_migration",
        "databaseOwners": {
            "pharma_intel": "pharma_migration",
            "temporal": "temporal_owner",
            "temporal_visibility": "visibility_owner",
        },
    }
    assert restore_database_records(manifest) == [
        ("pharma_intel", "pharma_migration"),
        ("pharma_intel", "pharma_migration", "postgres.dump"),
        ("temporal", "temporal_owner", "temporal.dump"),
        ("temporal_visibility", "visibility_owner", "temporal-visibility.dump"),
    ]


def test_preserves_the_documented_original_v1_identity() -> None:
    assert restore_database_records({"schemaVersion": 1, "database": "pharma_intel"})[1] == (
        "pharma_intel",
        "pharma_app",
        "postgres.dump",
    )


@pytest.mark.parametrize("database", ["postgres", "temporal", "../../data", "app;DROP DATABASE", True])
def test_rejects_reserved_or_unsafe_database_identities(database: object) -> None:
    with pytest.raises(ValueError):
        restore_database_records({"schemaVersion": 1, "database": database})


def test_does_not_guess_an_undeclared_custom_database_owner() -> None:
    with pytest.raises(ValueError, match="exact three"):
        restore_database_records({"schemaVersion": 1, "database": "custom_application"})


def test_rejects_partial_owner_metadata_instead_of_using_a_legacy_fallback() -> None:
    with pytest.raises(ValueError, match="administrator"):
        restore_database_records(
            {
                "schemaVersion": 1,
                "database": "pharma_intel",
                "databaseOwners": dict.fromkeys(["pharma_intel", "temporal", "temporal_visibility"], "owner"),
            }
        )
