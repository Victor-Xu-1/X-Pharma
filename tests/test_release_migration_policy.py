"""Source-bound current migration policy and frozen historical evidence contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.release import (
    ReleaseEvidenceError,
    _validate_specialized_evidence,
    assemble_bundle,
    capture_gate,
    load_policy,
    verify_bundle,
)
from scripts.release.contracts import migrations
from scripts.release.contracts.core import LEGACY_DATABASE_ALEMBIC_HEAD
from tests.test_release_evidence import (
    _commit_policy,
    _database_acceptance_statement,
    _policy,
    _repository,
    _runtime_acceptance_statement,
    _security,
)

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("category", ["database", "runtime"])
def test_current_report_accepts_exact_candidate_migration(tmp_path: Path, category: str) -> None:
    factory = _database_acceptance_statement if category == "database" else _runtime_acceptance_statement
    statement_path, statement, report, policy = factory(tmp_path)
    database = report["database"]
    assert isinstance(database, dict)
    database["alembic_head"] = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    _validate_specialized_evidence(statement_path, category, statement, policy=policy)


@pytest.mark.parametrize("category", ["database", "runtime"])
def test_current_policy_does_not_accept_historical_database_head(tmp_path: Path, category: str) -> None:
    factory = _database_acceptance_statement if category == "database" else _runtime_acceptance_statement
    statement_path, statement, report, policy = factory(tmp_path)
    database = report["database"]
    assert isinstance(database, dict)
    database["alembic_head"] = "5d7e1a3c9b24"
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="(migration|database authority)"):
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)


@pytest.mark.parametrize("category", ["database", "runtime"])
def test_actual_stdlib_report_program_matches_current_release_consumer(tmp_path: Path, category: str) -> None:
    factory = _database_acceptance_statement if category == "database" else _runtime_acceptance_statement
    _, statement, expected, policy = factory(tmp_path)
    actual = tmp_path / "actual"
    actual.mkdir()
    output = actual / "report.json"
    database = expected["database"]
    assert isinstance(database, dict)
    environment = os.environ.copy()
    if category == "database":
        script = ROOT / "scripts/verify-local-database.sh"
        inputs = []
        for name, key in (("rls", "rls"), ("search", "search"), ("hygiene", "runtime_hygiene")):
            path = actual / f"{name}.json"
            path.write_text(json.dumps(expected[key]), encoding="utf-8")
            inputs.append(str(path))
        arguments = [
            *inputs,
            str(output),
            str(database["postgresql_version"]),
            str(database["rdkit_version"]),
            str(database["alembic_head"]),
            "14",
        ]
    else:
        script = ROOT / "scripts/status.sh"
        entrypoints = expected["entrypoints"]
        assert isinstance(entrypoints, dict)
        web = entrypoints["web"]
        assert isinstance(web, dict)
        for name, value in (
            ("SERVICES_JSON", expected["services"]),
            ("SEARCH_JSON", expected["search"]),
            ("HYGIENE_JSON", expected["runtime_hygiene"]),
            ("WORKBENCH_JSON", web["workbenches"]),
        ):
            environment[name] = json.dumps(value)
        arguments = [
            str(output),
            str(database["alembic_head"]),
            str(database["postgresql_version"]),
            str(database["rdkit_version"]),
            "14",
        ]
    # Execute only the actual final stdlib report program, not its Docker/HTTP probes.
    program = script.read_text(encoding="utf-8").rsplit("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    result = subprocess.run(  # noqa: S603 - Fixed owned report code and synthetic metadata, no services.
        [sys.executable, "-S", "-", *arguments],
        input=program,
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output.stat().st_mode & 0o777 == 0o600
    _validate_specialized_evidence(actual / "gate-statement.json", category, statement, policy=policy)


@pytest.mark.parametrize("head", [None, True, 123, [], "", "b8f41d6c", "B8F41D6C2E93", "b8f41d6c2e93\n"])
def test_policy_rejects_malformed_explicit_migration_head(tmp_path: Path, head: object) -> None:
    path = _policy(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["database_alembic_head"] = head
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="invalid database migration head"):
        load_policy(path)


@pytest.mark.parametrize("condition", ["matching", "missing", "stale", "unknown", "multiple", "broken"])
def test_authoritative_policy_must_match_one_complete_source_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    root = tmp_path / "candidate"
    versions = root / "migrations/versions"
    versions.mkdir(parents=True)
    (root / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n", encoding="utf-8")
    policy_path = root / "deploy/release/evidence-policy.json"
    policy_path.parent.mkdir(parents=True)
    document = json.loads((ROOT / "deploy/release/evidence-policy.json").read_text(encoding="utf-8"))
    current = document["database_alembic_head"]
    (versions / "ancestor.py").write_text(
        f"revision = {LEGACY_DATABASE_ALEMBIC_HEAD!r}\ndown_revision = None\n",
        encoding="utf-8",
    )
    parent = "000000000000" if condition == "broken" else LEGACY_DATABASE_ALEMBIC_HEAD
    (versions / "current.py").write_text(f"revision = {current!r}\ndown_revision = {parent!r}\n", encoding="utf-8")
    if condition == "missing":
        document.pop("database_alembic_head")
    elif condition in {"stale", "unknown"}:
        document["database_alembic_head"] = LEGACY_DATABASE_ALEMBIC_HEAD if condition == "stale" else "000000000000"
    elif condition == "multiple":
        (versions / "foreign.py").write_text("revision = 'aabbccddeeff'\ndown_revision = None\n", encoding="utf-8")
    policy_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(migrations, "_SOURCE_ROOT", root)

    if condition == "matching":
        assert load_policy(policy_path).database_alembic_head == current
    elif condition == "broken":
        with pytest.warns(UserWarning, match="Revision 000000000000"):
            with pytest.raises(ReleaseEvidenceError, match="migration authority"):
                load_policy(policy_path)
    else:
        with pytest.raises(ReleaseEvidenceError, match="(candidate migration head|migration authority)"):
            load_policy(policy_path)


@pytest.mark.parametrize("category,version", [("database", 1), ("runtime", 1), ("runtime", 2), ("runtime", 3)])
def test_signed_historical_bundle_replays_its_frozen_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    version: int,
) -> None:
    repo = _repository(tmp_path)
    source = _policy(tmp_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    document["categories"] = {category: {"max_age_hours": 24}}
    document["levels"]["pilot"]["required_categories"] = [category]
    source.write_text(json.dumps(document), encoding="utf-8")
    policy_path = _commit_policy(repo, source)
    assert load_policy(policy_path).database_alembic_head == LEGACY_DATABASE_ALEMBIC_HEAD
    security = _security(tmp_path, repo)
    directory = tmp_path / "statement"
    directory.mkdir()
    factory = _database_acceptance_statement if category == "database" else _runtime_acceptance_statement
    statement_path, _, report, _ = factory(directory)
    database = report["database"]
    assert isinstance(database, dict)
    database["alembic_head"] = LEGACY_DATABASE_ALEMBIC_HEAD
    if category == "runtime":
        report["schema"] = f"pharma.local-runtime-acceptance.v{version}"
        report["schema_version"] = version
        entrypoints = report["entrypoints"]
        assert isinstance(entrypoints, dict)
        web = entrypoints["web"]
        assert isinstance(web, dict)
        if version == 1:
            web.pop("workbenches")
        elif version == 2:
            workbenches = web["workbenches"]
            assert isinstance(workbenches, dict)
            for workbench in workbenches.values():
                assert isinstance(workbench, dict)
                for key in ("entry_document", "workbench_marker", "document_sha256"):
                    workbench.pop(key)
    report_path = directory / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    _, exit_code = capture_gate(
        repo=repo,
        policy_path=policy_path,
        category=category,
        security_directory=security,
        output=statement_path,
        command=[sys.executable, "-c", "print('controlled historical report fixture')"],
        attachments=[report_path],
    )
    assert exit_code == 0
    signing_key = Ed25519PrivateKey.generate()
    private = tmp_path / "fixture-private.pem"
    private.touch(mode=0o600)
    private.write_bytes(
        signing_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    public = tmp_path / "fixture-public.pem"
    public.write_bytes(
        signing_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    bundle = tmp_path / "signed-bundle"
    assemble_bundle(
        repo=repo,
        policy_path=policy_path,
        level_name="pilot",
        security_directory=security,
        statements=[statement_path],
        output=bundle,
        signing_key_path=private,
        signing_key_id="controlled-fixture",
    )

    def current_source_is_not_historical_authority(_root: Path) -> str:
        raise AssertionError("a frozen evidence bundle must not resolve today's migration head")

    monkeypatch.setattr(migrations, "current_migration_head", current_source_is_not_historical_authority)
    verified: dict[str, Any] = verify_bundle(bundle, trusted_public_key=public)
    assert verified["status"] == "passed"
    assert verified["signature_verified"] is True
    assert verified["production_claim"] is False


@pytest.mark.parametrize("version", [1, 2])
def test_active_runtime_policy_rejects_report_schema_downgrade(tmp_path: Path, version: int) -> None:
    statement_path, statement, report, policy = _runtime_acceptance_statement(tmp_path)
    report["schema"] = f"pharma.local-runtime-acceptance.v{version}"
    report["schema_version"] = version
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="policy minimum"):
        _validate_specialized_evidence(statement_path, "runtime", statement, policy=policy)


@pytest.mark.parametrize(
    "category,version", [("database", True), ("database", 1.0), ("runtime", True), ("runtime", 3.0)]
)
def test_report_schema_version_is_an_integer_not_a_bool_or_float(
    tmp_path: Path, category: str, version: object
) -> None:
    factory = _database_acceptance_statement if category == "database" else _runtime_acceptance_statement
    statement_path, statement, report, policy = factory(tmp_path)
    report["schema_version"] = version
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="scope or status"):
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)
