"""Actual report-producer/consumer wiring with synthetic metadata, never a real restore."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from pharma_intel.platform.backup_contract import BACKUP_RESTORE_FIELDS_V1, BACKUP_RESTORE_SCHEMA_V1
from pharma_intel.platform.operations import _evidence_entries
from scripts.lib import runtime_backup_report
from scripts.lib.runtime_backup_report import build_report, write_exclusive
from scripts.release.backup_validation import _validate_backup_restore_evidence
from scripts.release.contracts.migrations import known_migration_revisions
from scripts.release.policy import load_policy
from scripts.release.records import ReleaseEvidenceError

ROOT = Path(__file__).parents[1]
BACKUP_IMAGE = "sha256:" + "1" * 64
TARGET_IMAGE = "sha256:" + "2" * 64


def producer_arguments(tmp_path: Path) -> list[str]:
    backup = tmp_path / "backups/release-candidates/controlled"
    return [
        str(backup / "manifest.json"),
        str(backup / "checksums.sha256"),
        str(tmp_path / "controlled-restore-result.json"),
        str(backup),
        str(tmp_path / "backups"),
        "120",
        str(tmp_path / "backup_restore/report.json"),
        TARGET_IMAGE,
    ]


def run_generator(tmp_path: Path, flags: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - The owned standard-library producer, synthetic metadata only.
        [sys.executable, *flags, str(ROOT / "scripts/lib/runtime_backup_report.py"), *producer_arguments(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def generate_report(tmp_path: Path, flags: tuple[str, ...] = ()) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    authority = tmp_path / "backups"
    backup = authority / "release-candidates" / "controlled"
    backup.mkdir(parents=True)
    files = [
        "postgres.dump",
        "postgres-globals.sql",
        "temporal.dump",
        "temporal-visibility.dump",
        "object-store.tar.gz",
        "markdown-wiki.tar.gz",
    ]
    checksums: list[str] = []
    artifacts: dict[str, dict[str, int]] = {}
    for name in files:
        payload = ("controlled report metadata fixture: " + name).encode()
        (backup / name).write_bytes(payload)
        artifacts[name] = {"sizeBytes": len(payload)}
        checksums.append(f"{hashlib.sha256(payload).hexdigest()}  {name}\n")
    (backup / "checksums.sha256").write_text("".join(checksums), encoding="utf-8")
    head = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    assert isinstance(head, str)
    manifest = {
        "authority": files,
        "artifacts": artifacts,
        "postgresImageId": BACKUP_IMAGE,
        "alembicHead": head,
        "rowCounts": {"public.alembic_version": 1},
    }
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    restored = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "main_runtime_modified": False,
        "rls_probe": "passed",
        "temporal_databases_restored": 2,
        "tables_verified": 1,
        "archives_verified": 2,
        "alembic_head": head,
        "rdkit_version": "4.8.0",
        "rdkit_function_probe": "passed",
        "backup_postgres_image_id": BACKUP_IMAGE,
        "restored_postgres_image_id": TARGET_IMAGE,
        "postgres_image_changed": True,
    }
    restore = tmp_path / "controlled-restore-result.json"
    restore.write_text(json.dumps(restored), encoding="utf-8")
    output = tmp_path / "backup_restore" / "report.json"
    output.parent.mkdir()
    source = (ROOT / "scripts/verify-local-backup-restore.sh").read_text()
    assert 'python3 "$root/scripts/lib/runtime_backup_report.py"' in source
    result = run_generator(tmp_path, flags)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert json.loads(result.stdout) == report
    assert output.stat().st_mode & 0o777 == 0o600
    statement = {
        "generated_at": report["generated_at"],
        "attachments": [{"path": "report.json"}],
        "subject": {"targets": {"postgres": "controlled-postgres@" + TARGET_IMAGE}},
    }
    return output, report, statement


def test_current_backup_producer_round_trips_through_release_and_readonly_platform(tmp_path: Path) -> None:
    output, report, statement = generate_report(tmp_path)
    arguments = producer_arguments(tmp_path)
    direct = build_report(
        Path(arguments[0]),
        Path(arguments[1]),
        Path(arguments[2]),
        Path(arguments[3]),
        Path(arguments[4]),
        int(arguments[5]),
        arguments[7],
    )
    assert direct == report
    direct_output = tmp_path / "direct-report.json"
    write_exclusive(direct_output, output.read_bytes())
    assert direct_output.read_bytes() == output.read_bytes()
    assert direct_output.stat().st_mode & 0o777 == 0o600
    policy = load_policy(ROOT / "deploy/release/evidence-policy.json")
    _validate_backup_restore_evidence(output.with_name("gate-statement.json"), statement, policy=policy)
    entries = {entry["category"]: entry for entry in _evidence_entries(tmp_path)}
    assert entries["backup_restore"]["status"] == "passed"
    assert report["production_claim"] is False and report["sensitive_backup_embedded"] is False
    assert report["backup_postgres_image_id"] == BACKUP_IMAGE
    assert report["restored_postgres_image_id"] == TARGET_IMAGE
    assert report["postgres_image_changed"] is True and report["rdkit_function_probe"] == "passed"


def test_report_producer_does_not_require_site_packages_or_installed_product_metadata(tmp_path: Path) -> None:
    _, report, _ = generate_report(tmp_path, ("-S",))
    assert report["schema"] == "pharma.local-backup-restore-acceptance.v2"
    assert report["schema_version"] == 2


def test_report_publication_is_exclusive_and_retains_existing_evidence(tmp_path: Path) -> None:
    output, _, _ = generate_report(tmp_path)
    original, timestamp = output.read_bytes(), output.stat().st_mtime_ns
    result = run_generator(tmp_path, ("-S",))
    assert result.returncode != 0 and "refusing to overwrite" in result.stderr
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_exclusive(output, b"must not replace existing evidence")
    assert output.read_bytes() == original and output.stat().st_mtime_ns == timestamp
    assert not list(output.parent.glob(".report.json.*.tmp"))


def test_cli_output_uses_the_same_validated_data_and_private_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, report, _ = generate_report(tmp_path)
    arguments = producer_arguments(tmp_path)
    output = tmp_path / "cli-report.json"
    arguments[6] = str(output)
    monkeypatch.setattr(sys, "argv", [str(ROOT / "scripts/lib/runtime_backup_report.py"), *arguments])
    runtime_backup_report.main()
    assert json.loads(capsys.readouterr().out) == json.loads(output.read_text()) == report
    assert output.stat().st_mode & 0o777 == 0o600


def test_cli_argument_errors_cannot_start_a_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["runtime_backup_report.py"])
    with pytest.raises(ValueError, match="usage: runtime_backup_report.py"):
        runtime_backup_report.main()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("uncontracted", True),
        ("schema_version", True),
        ("authority_artifacts", True),
        ("tables_verified", 0),
        ("duration_seconds", 0),
        ("credentials_recorded", True),
        ("production_claim", True),
        ("sensitive_backup_embedded", True),
        ("main_runtime_modified", True),
        ("backup_manifest_sha256", "not-a-digest"),
        ("backup_reference", "backups/../../outside"),
        ("backup_reference", "backups/release-candidates/..\\outside"),
        ("backup_reference", "backups/release-candidates/unsafe\nname"),
        ("temporal_databases_restored", 2.0),
        ("archives_verified", 2.0),
        ("rdkit_function_probe", "failed"),
        ("restored_postgres_image_id", "postgres:latest"),
        ("postgres_image_changed", False),
        ("postgres_image_changed", 1),
    ],
)
def test_current_report_cannot_omit_or_overclaim_its_required_contract(
    tmp_path: Path, field: str, value: object
) -> None:
    output, report, statement = generate_report(tmp_path)
    report[field] = value
    output.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError):
        _validate_backup_restore_evidence(
            output.with_name("gate-statement.json"),
            statement,
            policy=load_policy(ROOT / "deploy/release/evidence-policy.json"),
        )
    entries = {entry["category"]: entry for entry in _evidence_entries(tmp_path)}
    assert entries["backup_restore"]["status"] == "invalid"


@pytest.mark.parametrize("head", ["000000000000", "b8f41d"])
def test_current_release_rejects_unknown_or_abbreviated_backup_revisions(tmp_path: Path, head: str) -> None:
    output, report, statement = generate_report(tmp_path)
    report["alembic_head"] = head
    output.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="unknown migration"):
        _validate_backup_restore_evidence(output.with_name("gate-statement.json"), statement, policy=None)


@pytest.mark.parametrize(
    "subject", [None, {"targets": {"postgres": "mutable:latest"}}, {"targets": {"postgres": "release@" + BACKUP_IMAGE}}]
)
def test_upgrade_target_must_equal_the_security_scanned_subject(tmp_path: Path, subject: object) -> None:
    output, _, statement = generate_report(tmp_path)
    statement["subject"] = subject
    with pytest.raises(ReleaseEvidenceError, match="security-scanned"):
        _validate_backup_restore_evidence(output.with_name("gate-statement.json"), statement, policy=None)


def test_historical_policy_retains_v1_without_allowing_current_policy_to_downgrade(tmp_path: Path) -> None:
    output, report, statement = generate_report(tmp_path)
    legacy = {key: value for key, value in report.items() if key in BACKUP_RESTORE_FIELDS_V1}
    legacy.update(schema=BACKUP_RESTORE_SCHEMA_V1, schema_version=1, alembic_head="5d7e1a3c9b24")
    output.write_text(json.dumps(legacy), encoding="utf-8")
    current = load_policy(ROOT / "deploy/release/evidence-policy.json")
    with pytest.raises(ReleaseEvidenceError, match="policy minimum"):
        _validate_backup_restore_evidence(output.with_name("gate-statement.json"), statement, policy=current)
    snapshot = json.loads(current.path.read_text())
    assert snapshot["categories"]["backup_restore"].pop("minimum_report_schema_version") == 2
    archived = tmp_path / "archived-policy.json"
    archived.write_text(json.dumps(snapshot), encoding="utf-8")
    _validate_backup_restore_evidence(output.with_name("gate-statement.json"), statement, policy=load_policy(archived))
    entries = {entry["category"]: entry for entry in _evidence_entries(tmp_path)}
    assert entries["backup_restore"]["status"] == "passed"


@pytest.mark.parametrize("minimum", [0, -1, True, "2", 2.5, 1001])
def test_policy_minimum_report_version_is_strictly_typed_and_bounded(tmp_path: Path, minimum: object) -> None:
    document = json.loads((ROOT / "deploy/release/evidence-policy.json").read_text())
    document["categories"]["backup_restore"]["minimum_report_schema_version"] = minimum
    candidate = tmp_path / "policy.json"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="minimum report schema version"):
        load_policy(candidate)


@pytest.mark.parametrize(
    ("source", "field", "value"),
    [
        ("restore", "alembic_head", "unrelated"),
        ("restore", "tables_verified", 2),
        ("restore", "rdkit_function_probe", "failed"),
        ("restore", "backup_postgres_image_id", TARGET_IMAGE),
        ("restore", "restored_postgres_image_id", BACKUP_IMAGE),
        ("restore", "postgres_image_changed", False),
        ("manifest", "rowCounts", {}),
        ("manifest", "artifacts", {}),
    ],
)
def test_producer_cannot_publish_mismatched_or_incomplete_restore_metadata(
    tmp_path: Path, source: str, field: str, value: object
) -> None:
    output, _, _ = generate_report(tmp_path)
    path = tmp_path / (
        "controlled-restore-result.json"
        if source == "restore"
        else "backups/release-candidates/controlled/manifest.json"
    )
    document = json.loads(path.read_text())
    document[field] = value
    path.write_text(json.dumps(document), encoding="utf-8")
    output.unlink()
    arguments = producer_arguments(tmp_path)
    with pytest.raises(ValueError):
        build_report(
            Path(arguments[0]),
            Path(arguments[1]),
            Path(arguments[2]),
            Path(arguments[3]),
            Path(arguments[4]),
            int(arguments[5]),
            arguments[7],
        )
    result = run_generator(tmp_path, ("-S",))
    assert result.returncode != 0 and not result.stdout
    assert not output.exists() and not list(output.parent.glob(".report.json.*.tmp"))


@pytest.mark.parametrize("historical", [False, True])
def test_original_image_and_known_ancestor_restoration_keep_their_distinct_meaning(
    tmp_path: Path, historical: bool
) -> None:
    output, _, statement = generate_report(tmp_path)
    manifest_path = tmp_path / "backups/release-candidates/controlled/manifest.json"
    restore_path = tmp_path / "controlled-restore-result.json"
    manifest, restored = json.loads(manifest_path.read_text()), json.loads(restore_path.read_text())
    if historical:
        manifest["alembicHead"] = restored["alembic_head"] = "5d7e1a3c9b24"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    restored.update(restored_postgres_image_id=BACKUP_IMAGE, postgres_image_changed=False)
    restore_path.write_text(json.dumps(restored), encoding="utf-8")
    arguments = producer_arguments(tmp_path)
    arguments[-1] = ""
    output.unlink()
    result = subprocess.run(  # noqa: S603 - Actual stdlib producer and only controlled metadata.
        [sys.executable, "-S", str(ROOT / "scripts/lib/runtime_backup_report.py"), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["backup_postgres_image_id"] == report["restored_postgres_image_id"] == BACKUP_IMAGE
    assert report["postgres_image_changed"] is False
    if historical:
        assert report["alembic_head"] == "5d7e1a3c9b24"
    statement.pop("subject")
    _validate_backup_restore_evidence(
        output.with_name("gate-statement.json"),
        statement,
        policy=load_policy(ROOT / "deploy/release/evidence-policy.json"),
    )


def test_ambiguous_candidate_migration_authority_fails_closed(tmp_path: Path) -> None:
    versions = tmp_path / "migrations/versions"
    versions.mkdir(parents=True)
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n", encoding="utf-8")
    for revision in ("abc111", "abc222"):
        (versions / f"{revision}.py").write_text(
            f"revision = '{revision}'\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="exactly one head"):
        known_migration_revisions(tmp_path)
