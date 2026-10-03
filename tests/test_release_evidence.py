from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

import scripts.release as release_evidence
import scripts.release.capture as release_capture
from scripts.release import (
    SECURITY_REQUIRED_FILES,
    ReleaseEvidenceError,
    _rename_noreplace,
    _statement_category,
    _validate_specialized_evidence,
    assemble_bundle,
    audit_release,
    capture_gate,
    collect_release_statements,
    goal_completion_audit,
    load_goal_completion_matrix,
    load_policy,
    prepare_production_evidence_handoff,
    production_evidence_requirements,
    register_production_evidence,
    register_production_evidence_batch,
    repository_subject,
    validate_security_evidence,
    verify_bundle,
    verify_production_evidence_handoff,
    verify_production_evidence_handoff_offline,
)


def _git(repo: Path, *arguments: str) -> None:
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run(  # noqa: S603 - test fixture invokes fixed Git commands without a shell.
        [executable, "-C", str(repo), *arguments], check=True, capture_output=True
    )


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "release-test@example.invalid")
    _git(repo, "config", "user.name", "Release Test")
    (repo / "source.txt").write_text("release subject\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    _git(repo, "commit", "-m", "test subject")
    return repo


def _policy(tmp_path: Path, *, production: bool = False) -> Path:
    path = tmp_path / "evidence-policy.json"
    levels: dict[str, object] = {
        "pilot": {
            "require_release_security": False,
            "require_signed_git_tag": False,
            "require_bundle_signature": False,
            "required_categories": ["quality"],
        }
    }
    if production:
        levels["production"] = {
            "require_release_security": True,
            "require_signed_git_tag": True,
            "require_bundle_signature": True,
            "required_categories": ["quality"],
        }
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "security_max_age_hours": {name: 24 for name in levels},
                "categories": {"quality": {"max_age_hours": 24}},
                "levels": levels,
            }
        ),
        encoding="utf-8",
    )
    return path


def _compact_goal_matrix(directory: Path, categories: list[str]) -> Path:
    root = Path(__file__).parents[1]
    document = json.loads((root / "deploy" / "release" / "goal-section-19-matrix.json").read_text(encoding="utf-8"))
    for requirement in document["requirements"]:
        requirement["baseline_categories"] = categories
        requirement["production_categories"] = categories
    matrix = directory / "goal-section-19-matrix.json"
    matrix.write_text(json.dumps(document), encoding="utf-8")
    shutil.copyfile(
        root / "deploy" / "release" / "goal-section-19-matrix.schema.json",
        directory / "goal-section-19-matrix.schema.json",
    )
    return matrix


def _commit_policy(repo: Path, source: Path) -> Path:
    destination = repo / "deploy" / "release" / "evidence-policy.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    _git(repo, "add", "deploy/release/evidence-policy.json")
    _git(repo, "commit", "-m", "add release policy")
    return destination


def _security(tmp_path: Path, repo: Path, *, release_mode: bool = False) -> Path:
    subject = repository_subject(repo)
    directory = tmp_path / ("security-release" if release_mode else "security")
    directory.mkdir()
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": subject.commit,
        "git_worktree_state": "clean",
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": {
            "api": "example.invalid/pharma/api@sha256:" + "a" * 64,
            "postgres": "example.invalid/pharma/postgres@sha256:" + "b" * 64,
            "ocr": "example.invalid/pharma/ocr@sha256:" + "c" * 64,
        },
        "policies": {
            "release_mode": release_mode,
            "risk_acceptance_reference": "SEC-APPROVED" if release_mode else "",
            "unresolved_high_critical": {"api": 2, "postgres": 3, "ocr": 4},
        },
    }
    (directory / "evidence-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for filename in SECURITY_REQUIRED_FILES - {"evidence-manifest.json"}:
        (directory / filename).write_text('{"status":"passed"}\n', encoding="utf-8")
    return directory


def _capture(tmp_path: Path, repo: Path, policy: Path, security: Path) -> Path:
    statement = tmp_path / "capture" / "quality.json"
    attachment = statement.parent / "quality-result.json"
    statement.parent.mkdir()
    attachment.write_text('{"status":"passed","tests":12}\n', encoding="utf-8")
    document, exit_code = capture_gate(
        repo=repo,
        policy_path=policy,
        category="quality",
        security_directory=security,
        output=statement,
        command=[sys.executable, "-c", "raise SystemExit(0)"],
        attachments=[attachment],
    )
    assert exit_code == 0
    assert document["status"] == "passed"
    return statement


def test_capture_binds_clean_source_security_and_attachments(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    statement_path = _capture(tmp_path, repo, policy, security)
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    subject = repository_subject(repo)

    assert statement["subject"]["git_commit"] == subject.commit
    assert statement["subject"]["source_tree_sha256"] == subject.source_tree_sha256
    assert statement["execution"]["exit_code"] == 0
    assert statement["missing_attachments"] == []
    assert statement["attachments"][0]["path"] == "quality-result.json"

    (repo / "source.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="clean Git worktree"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="quality",
            security_directory=security,
            output=tmp_path / "dirty.json",
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            attachments=[],
        )


def test_failed_capture_is_preserved_but_cannot_enter_bundle(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "failed.json"
    statement, exit_code = capture_gate(
        repo=repo,
        policy_path=policy,
        category="quality",
        security_directory=security,
        output=output,
        command=[sys.executable, "-c", "raise SystemExit(7)"],
        attachments=[],
    )

    assert exit_code == 7
    assert statement["status"] == "failed"
    with pytest.raises(ReleaseEvidenceError, match="did not pass"):
        assemble_bundle(
            repo=repo,
            policy_path=policy,
            level_name="pilot",
            security_directory=security,
            statements=[output],
            output=tmp_path / "bundle",
        )


def test_failed_capture_preserves_log_when_expected_attachment_is_missing(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "failed-with-log" / "quality.json"
    expected_report = output.parent / "quality-result.json"
    log_path = output.parent / "quality.log"

    statement, exit_code = capture_gate(
        repo=repo,
        policy_path=policy,
        category="quality",
        security_directory=security,
        output=output,
        command=[sys.executable, "-c", "import sys; print('root cause'); raise SystemExit(23)"],
        attachments=[expected_report],
        log_attachment=log_path,
    )

    assert exit_code == 23
    assert statement["status"] == "failed"
    assert statement["execution"]["exit_code"] == 23
    assert statement["missing_attachments"] == ["quality-result.json"]
    assert [attachment["path"] for attachment in statement["attachments"]] == ["quality.log"]
    assert log_path.read_text(encoding="utf-8").strip() == "root cause"


def test_successful_capture_requires_every_expected_attachment(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "missing-success-report" / "quality.json"

    with pytest.raises(ReleaseEvidenceError, match="regular file"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="quality",
            security_directory=security,
            output=output,
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            attachments=[output.parent / "quality-result.json"],
        )

    assert not output.exists()


def test_failed_capture_rejects_missing_attachment_outside_statement_directory(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "unsafe-failed-report" / "quality.json"

    with pytest.raises(ReleaseEvidenceError, match="below the statement directory"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="quality",
            security_directory=security,
            output=output,
            command=[sys.executable, "-c", "raise SystemExit(7)"],
            attachments=[tmp_path / "outside-result.json"],
        )

    assert not output.exists()


def test_capture_can_bind_a_bounded_private_command_log(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "logged" / "quality.json"
    log_path = output.parent / "quality.log"

    statement, exit_code = capture_gate(
        repo=repo,
        policy_path=policy,
        category="quality",
        security_directory=security,
        output=output,
        command=[
            sys.executable,
            "-c",
            "import sys; print('stdout evidence'); print('stderr evidence', file=sys.stderr)",
        ],
        attachments=[],
        log_attachment=log_path,
    )

    assert exit_code == 0
    assert statement["log_attachment"] == "quality.log"
    assert statement["attachments"][0]["path"] == "quality.log"
    assert set(log_path.read_text(encoding="utf-8").splitlines()) == {"stdout evidence", "stderr evidence"}
    assert log_path.stat().st_mode & 0o077 == 0


def test_capture_rejects_log_outside_statement_directory(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)

    with pytest.raises(ReleaseEvidenceError, match="below the statement directory"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="quality",
            security_directory=security,
            output=tmp_path / "capture" / "quality.json",
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            attachments=[],
            log_attachment=tmp_path / "outside.log",
        )


def test_capture_enforces_log_limit_while_command_is_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "bounded" / "quality.json"
    monkeypatch.setattr(release_capture, "MAX_CAPTURE_LOG_BYTES", 32)

    with pytest.raises(ReleaseEvidenceError, match="32-byte safety limit"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="quality",
            security_directory=security,
            output=output,
            command=[sys.executable, "-c", "print('x' * 1024)"],
            attachments=[],
            log_attachment=output.parent / "quality.log",
        )

    assert not output.exists()
    assert (output.parent / "quality.log").stat().st_size <= 32


def test_evidence_publication_never_replaces_an_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.write_text("new\n", encoding="utf-8")
    destination.write_text("existing\n", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="refusing to overwrite evidence"):
        _rename_noreplace(source, destination)

    assert source.read_text(encoding="utf-8") == "new\n"
    assert destination.read_text(encoding="utf-8") == "existing\n"


def test_security_evidence_rejects_unexpected_artifacts(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    (security / "untracked-report.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="unexpected files"):
        validate_security_evidence(security, repository_subject(repo))


def test_unsigned_pilot_bundle_verifies_and_detects_tampering(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)
    bundle = tmp_path / "pilot-bundle"

    result = assemble_bundle(
        repo=repo,
        policy_path=policy,
        level_name="pilot",
        security_directory=security,
        statements=[statement],
        output=bundle,
    )

    assert result["status"] == "passed"
    assert result["signature_verified"] is False
    assert verify_bundle(bundle)["files_verified"] >= 5
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["gate_status"] == "evidence_complete"
    assert manifest["approval_status"] == "pending_deployment_approval"
    assert manifest["production_claim"] is False

    attachment = bundle / "evidence" / "quality" / "quality-result.json"
    attachment.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="digest mismatch"):
        verify_bundle(bundle)


def test_bundle_binds_and_recomputes_goal_completion_status(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path, production=True)
    _compact_goal_matrix(tmp_path, ["quality"])
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)
    bundle = tmp_path / "goal-bundle"

    result = assemble_bundle(
        repo=repo,
        policy_path=policy,
        level_name="pilot",
        security_directory=security,
        statements=[statement],
        output=bundle,
    )

    goal = result["goal_section_19"]
    assert goal["requirement_count"] == 24
    assert goal["production_complete"] is False
    assert (bundle / "policy" / "goal-section-19-matrix.json").is_file()
    assert verify_bundle(bundle)["goal_section_19"] == goal

    manifest_path = bundle / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["goal_section_19"]["requirements"][0]["status"] = "missing"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_path = bundle / "SHA256SUMS"
    checksum_lines = []
    for path in sorted(
        candidate for candidate in bundle.rglob("*") if candidate.is_file() and candidate != checksum_path
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {path.relative_to(bundle).as_posix()}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="GOAL completion status"):
        verify_bundle(bundle)


def test_verifier_rejects_semantic_forgery_after_checksums_are_rewritten(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)
    bundle = tmp_path / "semantic-bundle"
    assemble_bundle(
        repo=repo,
        policy_path=policy,
        level_name="pilot",
        security_directory=security,
        statements=[statement],
        output=bundle,
    )
    manifest_path = bundle / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["policy"]["required_categories"] = []
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = __import__("hashlib").sha256(manifest_path.read_bytes()).hexdigest()
    checksum_path = bundle / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    checksum_path.write_text(
        "\n".join(
            f"{digest}  release-manifest.json" if line.endswith("  release-manifest.json") else line for line in lines
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseEvidenceError, match="policy binding"):
        verify_bundle(bundle)


def test_verifier_rejects_rehashed_bundle_with_incomplete_security_inventory(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)
    bundle = tmp_path / "incomplete-security-bundle"
    assemble_bundle(
        repo=repo,
        policy_path=policy,
        level_name="pilot",
        security_directory=security,
        statements=[statement],
        output=bundle,
    )
    removed = bundle / "evidence" / "security" / "semgrep.json"
    removed.unlink()
    manifest_path = bundle / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [item for item in manifest["files"] if item["path"] != "evidence/security/semgrep.json"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_path = bundle / "SHA256SUMS"
    checksum_lines = []
    for path in sorted(
        candidate for candidate in bundle.rglob("*") if candidate.is_file() and candidate != checksum_path
    ):
        digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {path.relative_to(bundle).as_posix()}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="security evidence inventory"):
        verify_bundle(bundle)


def test_signed_bundle_requires_the_trusted_ed25519_key(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    policy = _policy(tmp_path)
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "release-private.pem"
    public_path = tmp_path / "release-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    bundle = tmp_path / "signed-bundle"

    result = assemble_bundle(
        repo=repo,
        policy_path=policy,
        level_name="pilot",
        security_directory=security,
        statements=[statement],
        output=bundle,
        signing_key_path=private_path,
        signing_key_id="release-test-v1",
    )

    assert result["signature_verified"] is True
    with pytest.raises(ReleaseEvidenceError, match="trusted Ed25519 public key"):
        verify_bundle(bundle)
    assert verify_bundle(bundle, public_path)["signature_verified"] is True


def test_production_policy_fails_closed_and_audit_lists_real_gaps(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    external_policy = _policy(tmp_path, production=True)
    policy = _commit_policy(repo, external_policy)
    security = _security(tmp_path, repo)
    statement = _capture(tmp_path, repo, policy, security)

    with pytest.raises(ReleaseEvidenceError, match="security gate run in release mode"):
        assemble_bundle(
            repo=repo,
            policy_path=policy,
            level_name="production",
            security_directory=security,
            statements=[statement],
            output=tmp_path / "production-bundle",
        )

    audit = audit_release(
        repo=repo,
        policy_path=policy,
        level_name="production",
        security_directory=security,
        statements=[],
        release_tag=None,
    )
    assert audit["status"] == "blocked"
    assert audit["missing_categories"] == ["quality"]
    assert "security evidence was not generated in release mode" in audit["blockers"]
    assert audit["production_claim"] is False

    with pytest.raises(ReleaseEvidenceError, match="committed authoritative evidence policy"):
        audit_release(
            repo=repo,
            policy_path=external_policy,
            level_name="production",
            security_directory=security,
            statements=[],
            release_tag=None,
        )


def test_default_policy_maps_every_commercial_release_blocker() -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")

    assert policy.levels["development"].required_categories == {
        "quality",
        "source_reproducibility",
        "database",
        "browser",
        "entry_consistency",
        "record_consistency",
        "anti_extraction_baseline",
        "mcp_protocol",
        "mcp_async_tasks",
        "mcp_commercial",
        "performance_baseline",
        "operations_contract",
        "parser_sandbox",
        "ocr",
        "ingestion_readiness",
        "runtime",
    }
    assert policy.levels["development"].require_bundle_signature is False
    assert policy.levels["production"].require_release_security is True
    assert policy.levels["production"].require_signed_git_tag is True
    assert policy.levels["production"].require_bundle_signature is True
    assert policy.levels["production"].required_categories == {
        "quality",
        "source_reproducibility",
        "database",
        "browser",
        "entry_consistency",
        "record_consistency",
        "anti_extraction_baseline",
        "mcp_protocol",
        "mcp_async_tasks",
        "mcp_commercial",
        "performance_baseline",
        "operations_contract",
        "parser_sandbox",
        "ocr",
        "ingestion_readiness",
        "backup_restore",
        "runtime",
        "ingestion_pilot",
        "ingestion",
        "kubernetes",
        "product_uat",
        "data_licensing",
        "external_services",
        "infrastructure_ha_pitr",
        "billing_provider",
        "mcp_sender_constraint",
        "anti_extraction",
        "performance",
        "penetration_test",
        "disaster_recovery",
        "operations_approval",
        "change_approval",
        "production_topology",
    }
    assert set(policy.production_contracts) == {
        "anti_extraction",
        "billing_provider",
        "change_approval",
        "data_licensing",
        "disaster_recovery",
        "external_services",
        "infrastructure_ha_pitr",
        "ingestion",
        "mcp_sender_constraint",
        "operations_approval",
        "penetration_test",
        "performance",
        "product_uat",
        "production_topology",
    }
    assert {"literature_coverage", "regulatory_coverage", "freshness_and_coverage_report"}.issubset(
        policy.production_contracts["data_licensing"].checks
    )
    assert "domain_coverage" not in policy.production_contracts["data_licensing"].checks
    assert policy.production_contracts["product_uat"].minimum_artifacts == 2
    assert policy.production_contracts["ingestion"].minimum_artifacts == 2
    assert policy.production_contracts["ingestion"].approval_roles == {"data_owner", "operations"}
    assert policy.production_contracts["production_topology"].minimum_artifacts == 4
    assert {
        "event_projection_profile",
        "identity_and_secrets",
        "live_cluster_probe",
        "observability",
        "ragflow_exit_plan",
    } <= policy.production_contracts["production_topology"].checks
    assert policy.levels["pilot"].required_categories >= {"ingestion_pilot", "backup_restore", "kubernetes"}


def test_goal_section_19_matrix_is_schema_valid_and_covers_every_requirement() -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    matrix_path = root / "deploy" / "release" / "goal-section-19-matrix.json"
    schema = json.loads(
        (root / "deploy" / "release" / "goal-section-19-matrix.schema.json").read_text(encoding="utf-8")
    )
    document = json.loads(matrix_path.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
    matrix = load_goal_completion_matrix(matrix_path, policy)

    assert len(matrix.requirements) == 24
    assert [requirement.ordinal for requirement in matrix.requirements] == list(range(1, 25))
    assert {
        group: sum(requirement.group == group for requirement in matrix.requirements)
        for group in {
            "product_data",
            "human_agent",
            "security_reliability_operations",
            "engineering_delivery",
        }
    } == {
        "product_data": 5,
        "human_agent": 8,
        "security_reliability_operations": 6,
        "engineering_delivery": 5,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_requirement", "exactly 24 requirements"),
        ("reordered_requirement", "requirement 1 identity"),
        ("unknown_category", "unknown categories"),
        ("wrong_goal_version", "matrix identity"),
        ("extra_field", "requirement 1 fields"),
        ("incomplete_release_bundle", "cover the complete release policy"),
    ],
)
def test_goal_section_19_matrix_rejects_structural_and_policy_tampering(
    tmp_path: Path, mutation: str, message: str
) -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    source = root / "deploy" / "release" / "goal-section-19-matrix.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    requirements = document["requirements"]
    if mutation == "missing_requirement":
        requirements.pop()
    elif mutation == "reordered_requirement":
        requirements[0], requirements[1] = requirements[1], requirements[0]
    elif mutation == "unknown_category":
        requirements[0]["production_categories"] = ["fabricated_evidence"]
    elif mutation == "wrong_goal_version":
        document["goal_version"] = "1.3.1"
    elif mutation == "extra_field":
        requirements[0]["production_claim"] = True
    else:
        requirements[22]["production_categories"].remove("production_topology")
    path = tmp_path / "goal-section-19-matrix.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        load_goal_completion_matrix(path, policy)


def test_goal_section_19_audit_distinguishes_pilot_baseline_from_production_proof() -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    matrix = load_goal_completion_matrix(root / "deploy" / "release" / "goal-section-19-matrix.json", policy)

    pilot = goal_completion_audit(
        matrix,
        present_categories=set(policy.levels["pilot"].required_categories),
        release_security_verified=False,
        signed_git_tag_verified=False,
        bundle_signature_verified=False,
        release_level="pilot",
        release_eligible=True,
    )
    assert pilot["proven_count"] == 0
    assert pilot["baseline_only_count"] == 24
    assert pilot["missing_count"] == 0
    assert pilot["production_complete"] is False

    production = goal_completion_audit(
        matrix,
        present_categories=set(policy.levels["production"].required_categories),
        release_security_verified=True,
        signed_git_tag_verified=True,
        bundle_signature_verified=True,
        release_level="production",
        release_eligible=True,
    )
    assert production["proven_count"] == 24
    assert production["baseline_only_count"] == 0
    assert production["missing_count"] == 0
    assert production["production_complete"] is True


def test_goal_section_19_audit_never_overclaims_an_ineligible_release() -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    matrix = load_goal_completion_matrix(root / "deploy" / "release" / "goal-section-19-matrix.json", policy)

    result = goal_completion_audit(
        matrix,
        present_categories=set(policy.levels["production"].required_categories),
        release_security_verified=True,
        signed_git_tag_verified=True,
        bundle_signature_verified=True,
        release_level="production",
        release_eligible=False,
    )

    assert result["proven_count"] == 24
    assert result["production_complete"] is False


def test_release_audit_embeds_goal_section_19_status_for_the_authoritative_matrix(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    root = Path(__file__).parents[1]
    release_root = repo / "deploy" / "release"
    release_root.mkdir(parents=True)
    for name in (
        "evidence-policy.json",
        "goal-section-19-matrix.json",
        "goal-section-19-matrix.schema.json",
    ):
        shutil.copyfile(root / "deploy" / "release" / name, release_root / name)
    (repo / "GOAL.md").write_text("# PIP-GOAL-001 v1.9.9\n", encoding="utf-8")
    _git(repo, "add", "GOAL.md", "deploy/release")
    _git(repo, "commit", "-m", "add release goal matrix")
    security = _security(tmp_path, repo)

    result = audit_release(
        repo=repo,
        policy_path=release_root / "evidence-policy.json",
        level_name="pilot",
        security_directory=security,
        statements=[],
        release_tag=None,
    )

    goal = result["goal_section_19"]
    assert result["status"] == "blocked"
    assert goal["schema"] == "pharma.goal-completion-audit.v1"
    assert goal["requirement_count"] == 24
    assert goal["missing_count"] == 24
    assert goal["production_complete"] is False


def test_browser_acceptance_semantics_require_every_viewport_quality_scenario(tmp_path: Path) -> None:
    now = datetime.now(UTC).isoformat()
    statement_path = tmp_path / "gate-statement.json"
    report_path = tmp_path / "report.json"
    scenarios = {
        "accessibility": True,
        "authenticated_navigation": True,
        "billing_dispute": True,
        "browser_quality": True,
        "web_vitals_rum": True,
        "chemistry": True,
        "chemistry_real_api": True,
        "comparison_export": True,
        "data_lifecycle": True,
        "domain_export": True,
        "result_pagination": True,
        "result_to_comparison": True,
        "cross_page_comparison": True,
        "deal_entity_query": True,
        "deal_asset_attribute_query": True,
        "deal_asset_multiselect_query": True,
        "deal_full_result_landscape": True,
        "deal_asset_correctness": True,
        "patent_result_correctness": True,
        "enterprise_administration": True,
        "external_login": True,
        "internal_login": True,
        "internal_workbench": True,
        "ingestion_replay": True,
        "loading_empty_error_recovery": True,
        "master_data_rollback": True,
        "monitoring": True,
        "permission_boundary": True,
        "real_permission_boundary": True,
        "real_target_dossier": True,
        "pipeline_intelligence": True,
        "pipeline_cross_domain_signals": True,
        "pipeline_cross_domain_navigation": True,
        "pipeline_dense_results": True,
        "pipeline_relationship_correctness": True,
        "clinical_full_result_landscape": True,
        "clinical_result_dense_fields": True,
        "clinical_normalized_drug_or": True,
        "clinical_role_correctness": True,
        "clinical_linked_program_correctness": True,
        "publication_governance": True,
        "public_login": True,
        "quality_operations": True,
        "quarantine_governance": True,
        "reflow_keyboard": True,
        "regulatory_intelligence": True,
        "regulatory_result_correctness": True,
        "regulatory_subscription": True,
        "saved_search_maintenance": True,
        "epidemiology_news_subscription": True,
        "news_result_correctness": True,
        "epidemiology_trend_correctness": True,
        "research_workbench": True,
        "initial_load_boundary": True,
        "session_recovery": True,
        "stable_deep_link": True,
        "table_preference_server_continuity": True,
        "query_cancellation": True,
        "professional_query_state_matrix": True,
        "professional_error_permission_matrix": True,
        "explorer_quick_detail_continuity": True,
        "knowledge_research_continuity": True,
        "evidence_research_continuity": True,
        "workspace_isolation": True,
    }
    report: dict[str, Any] = {
        "schema": "pharma.browser-acceptance.v9",
        "schema_version": 9,
        "generated_at": now,
        "status": "passed",
        "production_claim": False,
        "environment_kind": "local-controlled-browser",
        "base_url": "http://127.0.0.1:18380",
        "browser": {"channel": "chrome", "product": "Google Chrome", "version": "140.0.7339.81"},
        "tests": {
            "total": 44,
            "desktop_1440": 11,
            "desktop_1920": 11,
            "tablet_1024": 11,
            "mobile_390": 11,
            "failed": 0,
        },
        "scenarios": scenarios,
        "reflow": {
            "scope": "effective-css-viewport-equivalent",
            "css_widths": [320, 360, 720],
            "system_zoom_verified": False,
        },
        "performance": {
            "scope": "local-controlled-navigation",
            "thresholds": {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1},
            "projects": {
                key: {"cls": 0.01, "inp_ms": 64, "interaction_count": 3, "lcp_ms": 1200}
                for key in ("desktop_1440", "desktop_1920", "tablet_1024", "mobile_390")
            },
        },
        "visual_regression": {
            "baseline_kind": "repository-owned-controlled-workbench-states",
            "comparison": "pixel",
            "max_diff_pixel_ratio": 0.001,
            "projects": {
                "desktop_1440": {
                    "project": "desktop-1440",
                    "width": 1440,
                    "height": 900,
                    "baselines": {
                        "no_result": {"capture": "full-page", "sha256": "a" * 64},
                        "dense_results": {"capture": "table-shell", "sha256": "e" * 64},
                        "trial_outcomes": {"capture": "dossier-section", "sha256": "3" * 64},
                        "patent_timeline": {"capture": "dossier-section", "sha256": "4" * 64},
                        "deal_rights": {"capture": "dossier-section", "sha256": "5" * 64},
                    },
                },
                "desktop_1920": {
                    "project": "desktop-1920",
                    "width": 1920,
                    "height": 1080,
                    "baselines": {
                        "no_result": {"capture": "full-page", "sha256": "b" * 64},
                        "dense_results": {"capture": "table-shell", "sha256": "f" * 64},
                        "trial_outcomes": {"capture": "dossier-section", "sha256": "3" * 64},
                        "patent_timeline": {"capture": "dossier-section", "sha256": "4" * 64},
                        "deal_rights": {"capture": "dossier-section", "sha256": "5" * 64},
                    },
                },
                "tablet_1024": {
                    "project": "tablet-1024",
                    "width": 1024,
                    "height": 768,
                    "baselines": {
                        "no_result": {"capture": "full-page", "sha256": "c" * 64},
                        "dense_results": {"capture": "table-shell", "sha256": "1" * 64},
                        "trial_outcomes": {"capture": "dossier-section", "sha256": "3" * 64},
                        "patent_timeline": {"capture": "dossier-section", "sha256": "4" * 64},
                        "deal_rights": {"capture": "dossier-section", "sha256": "5" * 64},
                    },
                },
                "mobile_390": {
                    "project": "mobile-390",
                    "width": 390,
                    "height": 844,
                    "baselines": {
                        "no_result": {"capture": "full-page", "sha256": "d" * 64},
                        "dense_results": {"capture": "table-shell", "sha256": "2" * 64},
                        "trial_outcomes": {"capture": "dossier-section", "sha256": "3" * 64},
                        "patent_timeline": {"capture": "dossier-section", "sha256": "4" * 64},
                        "deal_rights": {"capture": "dossier-section", "sha256": "5" * 64},
                    },
                },
            },
        },
        "duration_ms": 1000,
        "temporary_accounts_after": 0,
        "temporary_entities_after": 0,
        "temporary_chemistry_fixtures_after": 0,
        "credentials_recorded": False,
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    statement = {"generated_at": now, "attachments": [{"path": "report.json"}]}

    _validate_specialized_evidence(statement_path, "browser", statement)

    report["browser"] = {"channel": "msedge", "product": "Microsoft Edge", "version": "140.0.3485.54"}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    _validate_specialized_evidence(statement_path, "browser", statement)

    report["browser"] = {"channel": "chrome", "product": "Microsoft Edge", "version": "140.0.3485.54"}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="invalid scope or status"):
        _validate_specialized_evidence(statement_path, "browser", statement)

    report["browser"] = {"channel": "chrome", "product": "Google Chrome", "version": "140.0.7339.81"}

    report["temporary_chemistry_fixtures_after"] = 1
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="invalid scope or status"):
        _validate_specialized_evidence(statement_path, "browser", statement)
    report["temporary_chemistry_fixtures_after"] = 0

    report["scenarios"] = {**scenarios, "permission_boundary": False}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="every contracted scenario"):
        _validate_specialized_evidence(statement_path, "browser", statement)

    report["scenarios"] = scenarios
    report["browser"] = {"channel": "chromium", "product": "Chromium", "version": "140.0.7339.81"}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="invalid scope or status"):
        _validate_specialized_evidence(statement_path, "browser", statement)

    report["browser"] = {"channel": "chrome", "product": "Google Chrome", "version": "140.0.7339.81"}
    report["tests"] = {**report["tests"], "tablet_1024": 0}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="inventory is incomplete"):
        _validate_specialized_evidence(statement_path, "browser", statement)

    report["tests"] = {
        "total": 44,
        "desktop_1440": 11,
        "desktop_1920": 11,
        "tablet_1024": 11,
        "mobile_390": 11,
        "failed": 0,
    }
    report["performance"]["projects"]["tablet_1024"]["lcp_ms"] = 2501
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="performance budget failed"):
        _validate_specialized_evidence(statement_path, "browser", statement)

    report["performance"]["projects"]["tablet_1024"]["lcp_ms"] = 1200
    report["visual_regression"]["projects"]["mobile_390"]["baselines"]["dense_results"]["sha256"] = "invalid"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="visual baseline inventory"):
        _validate_specialized_evidence(statement_path, "browser", statement)


def test_ingestion_readiness_evidence_preserves_the_real_source_boundary(tmp_path: Path) -> None:
    now = datetime.now(UTC).isoformat()
    statement_path = tmp_path / "gate-statement.json"
    report_path = tmp_path / "report.json"
    readiness = {
        "schema": "pharma.ingestion-readiness.v1",
        "schema_version": 1,
        "generated_at": now,
        "status": "ready_for_source_registration",
        "production_claim": False,
        "real_source_automatic_ingestion_verified": False,
        "runtime": {"checks": [{"code": "scheduler", "status": "pass"}]},
        "inventory": {"registered_source_count": 0, "blocked_source_count": 0},
        "connectors": [
            {
                "connector_id": connector_id,
                "incremental": True,
                "replayable": True,
                "immutable_snapshot_required": True,
            }
            for connector_id in (
                "folder-v1",
                "http-manifest-v1",
                "s3-snapshot-v1",
                "sftp-snapshot-v1",
                "smb-snapshot-v1",
            )
        ],
    }
    report = {
        "schema": "pharma.ingestion-platform-readiness-evidence.v1",
        "schema_version": 1,
        "generated_at": now,
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "real_source_automatic_ingestion_verified": False,
        "services": [
            {"service": service, "running": True, "health": "healthy"}
            for service in ("postgres", "opensearch", "temporal", "parser", "clamav", "worker")
        ],
        "readiness": readiness,
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    statement = {"generated_at": now, "attachments": [{"path": "report.json"}]}

    _validate_specialized_evidence(statement_path, "ingestion_readiness", statement)

    readiness["real_source_automatic_ingestion_verified"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="platform controls are incomplete"):
        _validate_specialized_evidence(statement_path, "ingestion_readiness", statement)


def _pilot_ingestion_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    statement_time = datetime.now(UTC)
    automatic_time = statement_time - timedelta(minutes=2)
    manual_time = statement_time - timedelta(minutes=1)
    source_id = "0b1db158-0dad-4195-9f0d-7f03f818cf40"

    def search() -> dict[str, object]:
        return {
            "cluster": {
                "aliases": {
                    "entities": ["pharma-entities-v2-pilot"],
                    "evidence": ["pharma-evidence-v2-pilot"],
                    "knowledge": ["pharma-knowledge-v2-pilot"],
                },
                "available": True,
                "cluster_name": "pharma-search",
                "cluster_status": "green",
                "error": None,
                "version": "3.7.0",
            },
            "deliveries": {"dead": 0, "processing": 0, "retry": 0, "succeeded": 3},
        }

    def governance() -> dict[str, object]:
        return {
            "configured_model": "governed-extractor-2026-07",
            "extraction_runs": 1,
            "successful_extraction_runs": 1,
            "failed_extraction_runs": 0,
            "configured_model_runs": 1,
            "input_tokens": 120,
            "output_tokens": 48,
            "segments": 1,
            "accounted_segments": 1,
            "staged_facts": 2,
            "quote_verified_facts": 2,
        }

    manual: dict[str, object] = {
        "schema": release_evidence.INGESTION_PILOT_SCHEMA,
        "schema_version": 2,
        "generated_at": manual_time.isoformat(),
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "source_id": source_id,
        "source_type": "s3_snapshot",
        "dataset_key": "licensed-patents",
        "license_id": "LICENSE-PATENT-2026",
        "source_files": {
            "schema_version": 1,
            "source_id": source_id,
            "source_type": "s3_snapshot",
            "connector_id": "s3-snapshot-v1",
            "authoritative_inventory": True,
            "discovered": 1,
            "stable": 1,
            "oversized": 0,
            "excluded": 0,
            "error_count": 0,
            "configuration_error_count": 0,
        },
        "versions": {
            "current": 1,
            "traceable": 1,
            "malware_scanned": 1,
            "processed": 1,
            "governable": 1,
            "governed": 1,
            "projected": 1,
            "failed": 0,
            "idempotent_second_scan": True,
        },
        "governance": governance(),
        "runs": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "state": "SUCCEEDED",
                "counters": {"discovered": 0, "unchanged": 1, "unstable": 0, "excluded": 0, "failed": 0},
            },
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "state": "SUCCEEDED",
                "counters": {"discovered": 0, "unchanged": 1, "unstable": 0, "excluded": 0, "failed": 0},
            },
        ],
        "search": search(),
        "source_content_created_by_test": False,
    }
    automatic: dict[str, object] = {
        "schema": release_evidence.AUTOMATIC_INGESTION_SCHEMA,
        "schema_version": 4,
        "generated_at": automatic_time.isoformat(),
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "source_id": source_id,
        "source_type": "s3_snapshot",
        "dataset_key": "licensed-patents",
        "license_id": "LICENSE-PATENT-2026",
        "trigger": {
            "mode": "temporal-scheduler",
            "outcome": "new_version",
            "manual_trigger_used": False,
            "source_schedule_mutated": False,
            "source_content_created_by_test": False,
            "scan_interval_seconds": 300,
            "initial_due_in_seconds": 10,
            "observed_elapsed_seconds": 20,
            "baseline_versions": 0,
            "observed_versions": 1,
            "new_versions": 1,
            "baseline_run_id": "00000000-0000-0000-0000-000000000000",
            "baseline_run_created_at": (automatic_time - timedelta(minutes=2)).isoformat(),
            "observed_run_created_at": (automatic_time - timedelta(minutes=1)).isoformat(),
            "policy_sha256": "d" * 64,
            "baseline_policy_runs": 0,
            "observed_policy_runs": 1,
        },
        "workflow": {
            "run_id": "33333333-3333-4333-8333-333333333333",
            "workflow_id": f"source-ingest-{source_id}-20260719T120000Z",
            "state": "SUCCEEDED",
            "counters": {"discovered": 1, "unchanged": 0, "unstable": 0, "excluded": 0, "failed": 0},
        },
        "versions": {
            "current": 1,
            "traceable": 1,
            "malware_scanned": 1,
            "processed": 1,
            "governable": 1,
            "governed": 1,
            "projected": 1,
            "failed": 0,
        },
        "governance": governance(),
        "search": search(),
    }
    manual_path = tmp_path / release_evidence.INGESTION_PILOT_REPORT
    automatic_path = tmp_path / release_evidence.AUTOMATIC_INGESTION_REPORT
    manual_path.write_text(json.dumps(manual), encoding="utf-8")
    automatic_path.write_text(json.dumps(automatic), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": statement_time.isoformat(),
        "attachments": [
            {"path": release_evidence.INGESTION_PILOT_REPORT},
            {"path": release_evidence.AUTOMATIC_INGESTION_REPORT},
        ],
    }
    return tmp_path / "gate-statement.json", statement, manual, automatic, policy


def _rewrite_pilot_ingestion_reports(
    tmp_path: Path,
    manual: dict[str, object],
    automatic: dict[str, object],
) -> None:
    (tmp_path / release_evidence.INGESTION_PILOT_REPORT).write_text(json.dumps(manual), encoding="utf-8")
    (tmp_path / release_evidence.AUTOMATIC_INGESTION_REPORT).write_text(json.dumps(automatic), encoding="utf-8")


def test_pilot_ingestion_evidence_requires_real_idempotent_and_unattended_source_processing(tmp_path: Path) -> None:
    statement_path, statement, _, _, policy = _pilot_ingestion_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


def test_pilot_ingestion_evidence_accepts_a_naturally_scheduled_unchanged_source(tmp_path: Path) -> None:
    statement_path, statement, manual, automatic, policy = _pilot_ingestion_statement(tmp_path)
    trigger = automatic["trigger"]
    workflow = automatic["workflow"]
    assert isinstance(trigger, dict) and isinstance(workflow, dict)
    trigger["outcome"] = "unchanged"
    trigger["baseline_versions"] = 1
    trigger["observed_versions"] = 1
    trigger["new_versions"] = 0
    trigger["baseline_policy_runs"] = 1
    trigger["observed_policy_runs"] = 1
    trigger["initial_due_in_seconds"] = 60
    trigger["observed_elapsed_seconds"] = 5
    workflow["counters"] = {
        "discovered": 0,
        "unchanged": 1,
        "unstable": 0,
        "excluded": 0,
        "failed": 0,
    }
    _rewrite_pilot_ingestion_reports(tmp_path, manual, automatic)

    _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


def test_pilot_ingestion_evidence_accepts_current_policy_reprocessing_without_a_new_source_version(
    tmp_path: Path,
) -> None:
    statement_path, statement, manual, automatic, policy = _pilot_ingestion_statement(tmp_path)
    trigger = automatic["trigger"]
    assert isinstance(trigger, dict)
    trigger["outcome"] = "policy_reprocess"
    trigger["baseline_versions"] = 1
    trigger["observed_versions"] = 1
    trigger["new_versions"] = 0
    trigger["baseline_policy_runs"] = 0
    trigger["observed_policy_runs"] = 1
    _rewrite_pilot_ingestion_reports(tmp_path, manual, automatic)

    _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


def test_pilot_ingestion_evidence_accepts_only_the_declared_capture_log_beyond_reports(tmp_path: Path) -> None:
    statement_path, statement, _, _, policy = _pilot_ingestion_statement(tmp_path)
    statement["log_attachment"] = "command.log"
    attachments = statement["attachments"]
    assert isinstance(attachments, list)
    attachments.append({"path": "command.log"})

    _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)

    attachments.append({"path": "unexpected.json"})
    with pytest.raises(ReleaseEvidenceError, match="exactly two governed"):
        _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("created_content", "schema, scope or status"),
        ("source_mismatch", "same licensed real source"),
        ("source_error", "source inventory is incomplete"),
        ("unstable_run", "run counters are invalid"),
        ("non_idempotent", "not idempotent"),
        ("untraceable_version", "fully governed and traceable"),
        ("ungoverned_version", "fully governed and traceable"),
        ("unaccounted_segment", "AI governance is incomplete"),
        ("unlocated_quote", "AI governance is incomplete"),
        ("projection_backlog", "OpenSearch projection evidence"),
        ("manual_trigger", "unchanged Temporal schedule"),
        ("schedule_mutation", "unchanged Temporal schedule"),
        ("no_new_version", "did not discover and govern a new source version"),
        ("stale_workflow_watermark", "not newer than the captured scheduler watermark"),
        ("missing_policy_reprocess", "current-policy source reprocessing"),
        ("invalid_policy_fingerprint", "unchanged Temporal schedule"),
        ("wrong_workflow", "workflow identity or state"),
        ("lost_versions", "changed the automatically governed source inventory"),
        ("time_order", "evidence window or order"),
        ("extra_field", "schema, scope or status"),
    ],
)
def test_pilot_ingestion_evidence_rejects_partial_or_fabricated_semantics(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, manual, automatic, policy = _pilot_ingestion_statement(tmp_path)
    if mutation == "created_content":
        manual["source_content_created_by_test"] = True
    elif mutation == "source_mismatch":
        automatic["license_id"] = "LICENSE-OTHER-2026"
    elif mutation == "source_error":
        source_files = manual["source_files"]
        assert isinstance(source_files, dict)
        source_files["error_count"] = 1
    elif mutation in {"unstable_run", "non_idempotent"}:
        runs = manual["runs"]
        assert isinstance(runs, list) and isinstance(runs[1], dict)
        counters = runs[1]["counters"]
        assert isinstance(counters, dict)
        counters["unstable" if mutation == "unstable_run" else "discovered"] = 1
    elif mutation == "untraceable_version":
        versions = manual["versions"]
        assert isinstance(versions, dict)
        versions["traceable"] = 0
    elif mutation == "ungoverned_version":
        versions = manual["versions"]
        assert isinstance(versions, dict)
        versions["governed"] = 0
    elif mutation in {"unaccounted_segment", "unlocated_quote"}:
        governance = automatic["governance"]
        assert isinstance(governance, dict)
        governance["accounted_segments" if mutation == "unaccounted_segment" else "quote_verified_facts"] = 0
    elif mutation == "projection_backlog":
        search = automatic["search"]
        assert isinstance(search, dict) and isinstance(search["deliveries"], dict)
        search["deliveries"]["retry"] = 1
    elif mutation in {"manual_trigger", "schedule_mutation"}:
        trigger = automatic["trigger"]
        assert isinstance(trigger, dict)
        trigger["manual_trigger_used" if mutation == "manual_trigger" else "source_schedule_mutated"] = True
    elif mutation == "no_new_version":
        trigger = automatic["trigger"]
        assert isinstance(trigger, dict)
        trigger["observed_versions"] = trigger["baseline_versions"]
        trigger["new_versions"] = 0
    elif mutation == "stale_workflow_watermark":
        trigger = automatic["trigger"]
        assert isinstance(trigger, dict)
        trigger["observed_run_created_at"] = "1969-12-31T23:59:59+00:00"
    elif mutation == "missing_policy_reprocess":
        trigger = automatic["trigger"]
        assert isinstance(trigger, dict)
        trigger["outcome"] = "policy_reprocess"
        trigger["baseline_versions"] = 1
        trigger["observed_versions"] = 1
        trigger["new_versions"] = 0
        trigger["baseline_policy_runs"] = 0
        trigger["observed_policy_runs"] = 0
    elif mutation == "invalid_policy_fingerprint":
        trigger = automatic["trigger"]
        assert isinstance(trigger, dict)
        trigger["policy_sha256"] = "not-a-sha256"
    elif mutation == "wrong_workflow":
        workflow = automatic["workflow"]
        assert isinstance(workflow, dict)
        workflow["workflow_id"] = "manual-ingestion-workflow"
    elif mutation == "lost_versions":
        manual_versions = manual["versions"]
        assert isinstance(manual_versions, dict)
        for name in ("current", "traceable", "malware_scanned", "processed"):
            manual_versions[name] = 2
    elif mutation == "time_order":
        automatic["generated_at"] = datetime.now(UTC).isoformat()
    else:
        manual["notes"] = "uncontracted"
    _rewrite_pilot_ingestion_reports(tmp_path, manual, automatic)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


def test_pilot_ingestion_evidence_requires_exactly_two_reports(tmp_path: Path) -> None:
    statement_path, statement, _, _, policy = _pilot_ingestion_statement(tmp_path)
    attachments = statement["attachments"]
    assert isinstance(attachments, list)
    attachments.pop()

    with pytest.raises(ReleaseEvidenceError, match="exactly two"):
        _validate_specialized_evidence(statement_path, "ingestion_pilot", statement, policy=policy)


def test_pilot_ingestion_json_schemas_match_runtime_contract(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    manual_schema = json.loads(
        (root / "deploy" / "release" / "ingestion-pilot-report.schema.json").read_text(encoding="utf-8")
    )
    automatic_schema = json.loads(
        (root / "deploy" / "release" / "automatic-ingestion-report.schema.json").read_text(encoding="utf-8")
    )

    assert manual_schema["properties"]["schema"]["const"] == release_evidence.INGESTION_PILOT_SCHEMA
    assert set(manual_schema["required"]) == release_evidence.INGESTION_PILOT_FIELDS
    assert set(manual_schema["$defs"]["sourceInventory"]["required"]) == release_evidence.INGESTION_SOURCE_FIELDS
    assert set(manual_schema["$defs"]["governance"]["required"]) == release_evidence.INGESTION_GOVERNANCE_FIELDS
    assert automatic_schema["properties"]["schema"]["const"] == release_evidence.AUTOMATIC_INGESTION_SCHEMA
    assert set(automatic_schema["required"]) == release_evidence.AUTOMATIC_INGESTION_FIELDS
    for definition in ("counters", "governance", "search"):
        assert automatic_schema["$defs"][definition] == manual_schema["$defs"][definition]
    _, _, _, automatic, _ = _pilot_ingestion_statement(tmp_path)
    Draft202012Validator.check_schema(automatic_schema)
    Draft202012Validator(automatic_schema).validate(automatic)


def _record_consistency_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.RECORD_CONSISTENCY_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        "activity_id": "11111111-1111-4111-8111-111111111111",
        "target_id": "22222222-2222-4222-8222-222222222222",
        "provenance_id": "33333333-3333-4333-8333-333333333333",
        "source_version_id": "44444444-4444-4444-8444-444444444444",
        "source_document_id": "55555555-5555-4555-8555-555555555555",
        "source_locator": "page=7;paragraph=2",
        "activity_sha256": "a" * 64,
        "provenance_sha256": "b" * 64,
        "export_row_sha256": "c" * 64,
        "web_operations": ["get_bioactivities", "get_record_provenance"],
        "mcp_tools": [
            "get_bioactivity_landscape",
            "get_record_provenance",
            "create_data_export",
            "get_data_export",
            "read_data_export",
        ],
        "mcp_protocol_version": "2025-11-25",
        "billed_operations": 3,
        "unique_settlements": 3,
        "export_dataset": "fact_provenance",
        "export_record_count": 1,
        "export_manifest_verified": True,
        "same_authority_identifiers": True,
        "same_source_version": True,
        "same_source_locator": True,
        "cleanup": {"api_stopped": True, "mcp_stopped": True, "database_dropped": True},
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_record_consistency_evidence_requires_web_mcp_export_authority_contract(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _record_consistency_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "record_consistency", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("missing_tool", "operation inventory"),
        ("duplicate_settlement", "authority or commercial"),
        ("unsigned_export", "authority or commercial"),
        ("source_drift", "authority or commercial"),
        ("database_retained", "cleanup"),
    ],
)
def test_record_consistency_evidence_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _record_consistency_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "missing_tool":
        tools = report["mcp_tools"]
        assert isinstance(tools, list)
        tools.pop()
    elif mutation == "duplicate_settlement":
        report["unique_settlements"] = 2
    elif mutation == "unsigned_export":
        report["export_manifest_verified"] = False
    elif mutation == "source_drift":
        report["same_source_version"] = False
    else:
        cleanup = report["cleanup"]
        assert isinstance(cleanup, dict)
        cleanup["database_dropped"] = False
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "record_consistency", statement, policy=policy)


def _mcp_async_task_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    authority_digest = "a" * 64
    clients = [
        {
            "client": client,
            "client_version": version,
            "tasks_created": 2,
            "completed_tasks": 1,
            "cancelled_tasks": 1,
            "result_pages": 2,
            "unique_records": 2,
            "entity_ids_sha256": authority_digest,
            "manifest_sha256": digest * 64,
            "tampered_cursor_rejected": True,
            "recovered_after_error": True,
            "settlement_created": True,
            "credentials_recorded": False,
            "status": "passed",
        }
        for client, version, digest in (
            ("MCP Inspector", "0.22.0", "b"),
            ("Python MCP SDK", "1.28.1", "c"),
        )
    ]
    report: dict[str, object] = {
        "schema": release_evidence.MCP_ASYNC_TASK_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql-object-store",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        "protocol_version": "2025-11-25",
        "client_count": 2,
        "clients": clients,
        "same_authority_record_set": True,
        "database": {
            "tasks": 4,
            "completed_tasks": 2,
            "cancelled_tasks": 2,
            "settlements": 2,
            "signed_completed_tasks": 2,
            "active_reservations_after": 0,
        },
        "assertions": {key: True for key in release_evidence.MCP_ASYNC_TASK_ASSERTIONS},
        "cleanup": {
            "api_stopped": True,
            "mcp_stopped": True,
            "database_dropped": True,
            "temporary_object_store_destroyed": True,
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_mcp_async_task_evidence_requires_two_privileged_clients_and_destroyed_fixture(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _mcp_async_task_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "mcp_async_tasks", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("missing_client", "client inventory"),
        ("authority_drift", "different authority"),
        ("settlement_missing", "accounting"),
        ("assertion_missing", "assertions"),
        ("database_retained", "cleanup"),
    ],
)
def test_mcp_async_task_evidence_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _mcp_async_task_statement(tmp_path)
    clients = report["clients"]
    assert isinstance(clients, list)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "missing_client":
        clients.pop()
    elif mutation == "authority_drift":
        second = clients[1]
        assert isinstance(second, dict)
        second["entity_ids_sha256"] = "d" * 64
    elif mutation == "settlement_missing":
        database = report["database"]
        assert isinstance(database, dict)
        database["settlements"] = 1
    elif mutation == "assertion_missing":
        assertions = report["assertions"]
        assert isinstance(assertions, dict)
        assertions["result_pagination"] = False
    else:
        cleanup = report["cleanup"]
        assert isinstance(cleanup, dict)
        cleanup["database_dropped"] = False
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "mcp_async_tasks", statement, policy=policy)


def _anti_extraction_baseline_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.ANTI_EXTRACTION_BASELINE_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        "auth_profile": "isolated-database-api-key",
        "production_oidc_covered": False,
        "protocol_version": "2025-11-25",
        "scenarios": dict(release_evidence.ANTI_EXTRACTION_BASELINE_SCENARIOS),
        "database": {
            "durable_denial_reason_count": 4,
            "successful_settlement_count": 9,
            "active_reservations_after": 0,
            "unauthorized_export_jobs_created": 0,
            "credential_revocation_audit_events": 1,
            "raw_partition_values_persisted": False,
            "raw_correlation_values_persisted": False,
        },
        "cleanup": {"api_stopped": True, "mcp_stopped": True, "database_dropped": True},
        "assertions": {name: True for name in release_evidence.ANTI_EXTRACTION_BASELINE_ASSERTIONS},
        "duration_seconds": 12.5,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_anti_extraction_baseline_requires_full_protocol_and_durable_control_contract(
    tmp_path: Path,
) -> None:
    statement_path, statement, _, policy = _anti_extraction_baseline_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "anti_extraction_baseline", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("production_oidc", "scope or status"),
        ("extra_field", "scope or status"),
        ("missing_scenario", "scenario inventory"),
        ("failed_assertion", "assertions"),
        ("too_few_settlements", "database evidence"),
        ("raw_network", "database evidence"),
        ("database_retained", "cleanup"),
        ("zero_duration", "duration"),
    ],
)
def test_anti_extraction_baseline_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _anti_extraction_baseline_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "production_oidc":
        report["production_oidc_covered"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "missing_scenario":
        scenarios = report["scenarios"]
        assert isinstance(scenarios, dict)
        scenarios.pop("network_rotation")
    elif mutation == "failed_assertion":
        assertions = report["assertions"]
        assert isinstance(assertions, dict)
        assertions["unauthorized_export_denied"] = False
    elif mutation == "too_few_settlements":
        database = report["database"]
        assert isinstance(database, dict)
        database["successful_settlement_count"] = 8
    elif mutation == "raw_network":
        database = report["database"]
        assert isinstance(database, dict)
        database["raw_correlation_values_persisted"] = True
    elif mutation == "database_retained":
        cleanup = report["cleanup"]
        assert isinstance(cleanup, dict)
        cleanup["database_dropped"] = False
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "anti_extraction_baseline", statement, policy=policy)


def _backup_restore_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.BACKUP_RESTORE_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "credentials_recorded": False,
        "backup_reference": "backups/release-candidates/runtime-20260719-120000",
        "backup_manifest_sha256": "a" * 64,
        "backup_checksums_sha256": "b" * 64,
        "authority_artifacts": 8,
        "authority_bytes": 4096,
        "tables_verified": 42,
        "alembic_head": "5d7e1a3c9b24",
        "rdkit_version": "4.8.0",
        "temporal_databases_restored": 2,
        "rls_probe": "passed",
        "archives_verified": 2,
        "main_runtime_modified": False,
        "duration_seconds": 120,
        "sensitive_backup_embedded": False,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_backup_restore_evidence_requires_an_isolated_authority_restore(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _backup_restore_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "backup_restore", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("unsafe_reference", "reference is unsafe"),
        ("bad_hash", "digests"),
        ("wrong_head", "assertions"),
        ("no_tables", "inventory"),
        ("wrong_temporal_count", "assertions"),
        ("modified_runtime", "assertions"),
        ("sensitive_backup", "assertions"),
        ("zero_duration", "duration"),
    ],
)
def test_backup_restore_evidence_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _backup_restore_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "unsafe_reference":
        report["backup_reference"] = "backups/release-candidates/../../etc/shadow"
    elif mutation == "bad_hash":
        report["backup_manifest_sha256"] = "not-a-digest"
    elif mutation == "wrong_head":
        report["alembic_head"] = "000000000000"
    elif mutation == "no_tables":
        report["tables_verified"] = 0
    elif mutation == "wrong_temporal_count":
        report["temporal_databases_restored"] = 1
    elif mutation == "modified_runtime":
        report["main_runtime_modified"] = True
    elif mutation == "sensitive_backup":
        report["sensitive_backup_embedded"] = True
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "backup_restore", statement, policy=policy)


def _kubernetes_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.KUBERNETES_VALIDATION_SCHEMA,
        "schema_version": 3,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-isolated-kind",
        "production_claim": False,
        "credentials_recorded": False,
        "controlled_cluster": True,
        "cluster": "pharma-schema-20260719-120000-1234",
        "kind_version": "0.31.0",
        "kubernetes_server_version": "v1.35.0",
        "kind_node_image": "kindest/node:v1.35.0@sha256:" + "c" * 64,
        "cluster_topology": {"control_plane_nodes": 1, "worker_nodes": 2, "worker_zones": 2},
        "server_side_dry_run": "passed",
        "clamav_ha": {
            "image": "clamav/clamav:1.4@sha256:" + "a" * 64,
            "live_image_reference": "clamav/clamav:1.4",
            "live_image_pull_policy": "Never",
            "source_image_digest_verified": True,
            "workload": "StatefulSet",
            "replicas_requested": 2,
            "ready_replicas_before": 2,
            "ready_replicas_after": 2,
            "ready_endpoints_before": 2,
            "ready_endpoints_after": 2,
            "minimum_ready_endpoints_during_replacement": 1,
            "distinct_nodes_before": 2,
            "distinct_nodes_after": 2,
            "distinct_zones_before": 2,
            "distinct_zones_after": 2,
            "placement_identity_preserved": True,
            "distinct_pvcs": 2,
            "pvc_identity_preserved": True,
            "persistent_marker_preserved": True,
            "signature_freshness": "passed",
            "clean_scan": "passed",
            "eicar_blocked": True,
            "replacement_pod_uid_changed": True,
        },
        "production_crd_sets": 3,
        "cluster_cleanup": "passed",
        "duration_seconds": 90,
        "download_transport": "sha256-verified-content-cache",
        "asset_cache": {"content_addressed": True, "hits": 4, "misses": 0},
        "downloads": {
            "envoy_gateway": {"version": "v1.6.0", "sha256": "d" * 64},
            "external_secrets": {"version": "v0.19.2", "sha256": "e" * 64},
            "opentelemetry_operator": {"version": "v0.131.0", "sha256": "f" * 64},
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_kubernetes_evidence_requires_a_pinned_disposable_api_server(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _kubernetes_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "kubernetes", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("unpinned_image", "pinned runtime"),
        ("wrong_server", "pinned runtime"),
        ("dry_run_failed", "API-server validation"),
        ("cluster_retained", "API-server validation"),
        ("single_node", "cluster topology"),
        ("clamav_failover", "ClamAV high-availability"),
        ("clamav_placement", "ClamAV high-availability"),
        ("cache_count", "cache evidence"),
        ("bad_hash", "dependency metadata"),
        ("zero_duration", "duration"),
    ],
)
def test_kubernetes_evidence_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _kubernetes_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "unpinned_image":
        report["kind_node_image"] = "kindest/node:v1.35.0"
    elif mutation == "wrong_server":
        report["kubernetes_server_version"] = "v1.34.0"
    elif mutation == "dry_run_failed":
        report["server_side_dry_run"] = "failed"
    elif mutation == "cluster_retained":
        report["cluster_cleanup"] = "retained"
    elif mutation == "single_node":
        report["cluster_topology"] = {"control_plane_nodes": 1, "worker_nodes": 1, "worker_zones": 1}
    elif mutation == "clamav_failover":
        clamav_ha = report["clamav_ha"]
        assert isinstance(clamav_ha, dict)
        clamav_ha["minimum_ready_endpoints_during_replacement"] = 0
    elif mutation == "clamav_placement":
        clamav_ha = report["clamav_ha"]
        assert isinstance(clamav_ha, dict)
        clamav_ha["distinct_nodes_after"] = 1
    elif mutation == "cache_count":
        report["asset_cache"] = {"content_addressed": True, "hits": 2, "misses": 1}
    elif mutation == "bad_hash":
        downloads = report["downloads"]
        assert isinstance(downloads, dict)
        dependency = downloads["envoy_gateway"]
        assert isinstance(dependency, dict)
        dependency["sha256"] = "not-a-digest"
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "kubernetes", statement, policy=policy)


def _entry_consistency_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.ENTRY_CONSISTENCY_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-controlled-fixture",
        "production_claim": False,
        "credentials_recorded": False,
        "entity_id": "11111111-1111-4111-8111-111111111111",
        "canonical_entity_sha256": "a" * 64,
        "fields_compared": list(release_evidence.ENTRY_CONSISTENCY_ENTITY_FIELDS),
        "web_operations": ["create_entity", "get_entity", "search_entities"],
        "mcp_tools": ["get_entity", "search_entities"],
        "mcp_protocol_version": "2025-11-25",
        "mcp_billed_calls": 2,
        "unique_settlements": 2,
        "same_tenant_fixture": True,
        "same_filtered_facts": True,
        "temporary_accounts_after": 0,
        "temporary_entities_after": 0,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_entry_consistency_evidence_requires_same_web_and_billed_mcp_facts(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _entry_consistency_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "entry_consistency", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("field_omitted", "assertions"),
        ("protocol_drift", "assertions"),
        ("duplicate_settlement", "assertions"),
        ("fact_drift", "assertions"),
        ("fixture_retained", "assertions"),
    ],
)
def test_entry_consistency_evidence_rejects_drift_or_cleanup_failures(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _entry_consistency_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "field_omitted":
        fields = report["fields_compared"]
        assert isinstance(fields, list)
        fields.pop()
    elif mutation == "protocol_drift":
        report["mcp_protocol_version"] = "2026-01-01"
    elif mutation == "duplicate_settlement":
        report["unique_settlements"] = 1
    elif mutation == "fact_drift":
        report["same_filtered_facts"] = False
    else:
        report["temporary_entities_after"] = 1
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "entry_consistency", statement, policy=policy)


def _mcp_interoperability_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    target_id = "22222222-2222-4222-8222-222222222222"
    query_digest = "b" * 64
    contract_digest = "c" * 64
    pagination_digest = "d" * 64
    inspector = {
        "billed_calls": 5,
        "client": "MCP Inspector",
        "pageable_cursor_tools": 16,
        "query_sha256": query_digest,
        "status": "passed",
        "target_id": target_id,
        "tool_contract_sha256": contract_digest,
        "tools": release_evidence.MCP_INTEROPERABILITY_TOOL_COUNT,
        "usage_settlements": 10,
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": pagination_digest,
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": 1,
        "cross_domain_tool": "get_competitive_pipeline",
    }
    sdk = {
        "billed_calls": 5,
        "client": "Python MCP SDK",
        "client_version": "1.28.1",
        "protocol_version": "2025-11-25",
        "query_sha256": query_digest,
        "server_name": "X-Pharma",
        "server_version": "0.1.0",
        "status": "passed",
        "target_id": target_id,
        "tool_contract_sha256": contract_digest,
        "tools": release_evidence.MCP_INTEROPERABILITY_TOOL_COUNT,
        "usage_settlements": 13,
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": pagination_digest,
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": 1,
        "cross_domain_tool": "get_competitive_pipeline",
    }
    report: dict[str, object] = {
        "schema": release_evidence.MCP_INTEROPERABILITY_SCHEMA,
        "schema_version": 3,
        "created_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-controlled-fixture",
        "production_claim": False,
        "credentials_recorded": False,
        "client": "MCP Inspector + Python MCP SDK",
        "client_count": 2,
        "clients": [inspector, sdk],
        "inspector_version": "0.22.0",
        "python_sdk_version": "1.28.1",
        "protocol_version": "2025-11-25",
        "billed_calls": 10,
        "pageable_cursor_tools": 16,
        "query_sha256": query_digest,
        "target_id": target_id,
        "tool_contract_sha256": contract_digest,
        "tools": release_evidence.MCP_INTEROPERABILITY_TOOL_COUNT,
        "usage_settlements": 13,
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": pagination_digest,
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": 1,
        "cross_domain_tool": "get_competitive_pipeline",
        "workflow_assertions": dict(release_evidence.MCP_INTEROPERABILITY_WORKFLOW_ASSERTIONS),
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_mcp_interoperability_evidence_requires_both_pinned_clients(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _mcp_interoperability_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "mcp_protocol", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("sdk_drift", "protocol or tool contract"),
        ("product_version_drift", "version or settlement evidence"),
        ("product_name_drift", "version or settlement evidence"),
        ("tool_count", "protocol or tool contract"),
        ("contract_drift", "same billed contract"),
        ("client_failed", "same billed contract"),
        ("billing_missing", "same billed contract"),
        ("settlement_drift", "settlement evidence"),
        ("pagination_drift", "same billed contract"),
        ("recovery_missing", "protocol or tool contract"),
        ("workflow_drift", "protocol or tool contract"),
    ],
)
def test_mcp_interoperability_evidence_rejects_client_or_contract_drift(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _mcp_interoperability_statement(tmp_path)
    clients = report["clients"]
    assert isinstance(clients, list)
    sdk = clients[1]
    assert isinstance(sdk, dict)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "sdk_drift":
        report["python_sdk_version"] = "9.9.9"
    elif mutation == "product_version_drift":
        sdk["server_version"] = "1.28.1"
    elif mutation == "product_name_drift":
        sdk["server_name"] = "Pharma Intelligence"
    elif mutation == "tool_count":
        report["tools"] = 22
    elif mutation == "contract_drift":
        sdk["tool_contract_sha256"] = "d" * 64
    elif mutation == "client_failed":
        sdk["status"] = "failed"
    elif mutation == "billing_missing":
        sdk["billed_calls"] = 2
    elif mutation == "pagination_drift":
        sdk["pagination_entity_ids_sha256"] = "e" * 64
    elif mutation == "recovery_missing":
        report["recovered_after_error"] = False
    elif mutation == "workflow_drift":
        assertions = report["workflow_assertions"]
        assert isinstance(assertions, dict)
        assertions["error_recovery"] = False
    else:
        report["usage_settlements"] = 12
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "mcp_protocol", statement, policy=policy)


def _mcp_commercial_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.MCP_COMMERCIAL_SCHEMA,
        "schema_version": "2.0",
        "status": "passed",
        "environment": "local-or-ci-controlled-baseline",
        "production_claim": False,
        "credentials_recorded": False,
        "started_at": generated_at,
        "finished_at": generated_at,
        "protocol_version": "2025-11-25",
        "requests": {
            "requested": 40,
            "completed": 40,
            "failed": 0,
            "concurrency": 8,
            "duration_seconds": 2.5,
            "throughput_rps": 16.0,
        },
        "latency_ms": {"minimum": 100.0, "p50": 400.0, "p95": 700.0, "p99": 800.0, "maximum": 800.0},
        "billing": {
            "settlements_before": 100,
            "settlements_after": 140,
            "settlement_delta": 40,
            "unique_settlement_ids": 40,
            "active_reservations_after": 0,
        },
        "assertions": {name: True for name in release_evidence.MCP_COMMERCIAL_ASSERTIONS},
        "errors": [],
        "resilience": {
            "idempotency": {
                "same_settlement": True,
                "replay_flag": True,
                "argument_conflict_rejected": True,
            },
            "failure_release": {
                "domain_failure_rejected": True,
                "budget_failure_rejected": True,
                "active_reservations_after": 0,
                "reserved_units_after": "0E-8",
            },
            "cancellation": {"cancellation_requested": True, "outcome": "cancelled"},
            "timeout": {
                "timeout_observed": True,
                "outcome": "released",
                "replay_rejected_as_released": True,
                "reserved_retries": 0,
                "recovery_seconds": 0.25,
            },
            "reconciliation": {
                "settlement_delta": 1,
                "charged_units_delta": "1.00100000",
                "consumed_units_delta": "1.00100000",
                "balance_identity_holds": True,
            },
            "assertions": {name: True for name in release_evidence.MCP_COMMERCIAL_RESILIENCE_ASSERTIONS},
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_mcp_commercial_evidence_requires_bounded_unique_durable_billing(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _mcp_commercial_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "mcp_commercial", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("failed_baseline", "baseline assertions"),
        ("incomplete_requests", "request results"),
        ("latency_order", "latency contract"),
        ("billing_drift", "settlement evidence"),
        ("errors", "request failures"),
        ("resilience_failed", "resilience assertions"),
        ("reservation_leak", "accounting evidence"),
        ("timeout_not_durable", "released timeout"),
    ],
)
def test_mcp_commercial_evidence_rejects_billing_or_resilience_gaps(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _mcp_commercial_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "failed_baseline":
        assertions = report["assertions"]
        assert isinstance(assertions, dict)
        assertions["all_requests_succeeded"] = False
    elif mutation == "incomplete_requests":
        requests = report["requests"]
        assert isinstance(requests, dict)
        requests["completed"] = 39
    elif mutation == "latency_order":
        latency = report["latency_ms"]
        assert isinstance(latency, dict)
        latency["p95"] = 2100.0
    elif mutation == "billing_drift":
        billing = report["billing"]
        assert isinstance(billing, dict)
        billing["unique_settlement_ids"] = 39
    elif mutation == "errors":
        report["errors"] = [{"error_type": "RuntimeError"}]
    elif mutation == "resilience_failed":
        resilience = report["resilience"]
        assert isinstance(resilience, dict)
        assertions = resilience["assertions"]
        assert isinstance(assertions, dict)
        assertions["idempotent_replay_reuses_settlement"] = False
    elif mutation == "reservation_leak":
        resilience = report["resilience"]
        assert isinstance(resilience, dict)
        failure_release = resilience["failure_release"]
        assert isinstance(failure_release, dict)
        failure_release["active_reservations_after"] = 1
    else:
        resilience = report["resilience"]
        assert isinstance(resilience, dict)
        timeout = resilience["timeout"]
        assert isinstance(timeout, dict)
        timeout["replay_rejected_as_released"] = False
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "mcp_commercial", statement, policy=policy)


def _database_acceptance_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.DATABASE_ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "credentials_recorded": False,
        "database": {
            "postgresql_version": "18.4 (Debian 18.4-1.pgdg13+1)",
            "rdkit_version": "4.8.0",
            "alembic_head": "5d7e1a3c9b24",
            "migration_drift": False,
        },
        "rls": {
            "bypass_rls": False,
            "forged_context_rows": 0,
            "no_context_rows": 0,
            "passed": True,
            "runtime_role": "pharma_runtime",
            "signed_context_rows": 1,
            "signed_context_valid": True,
            "superuser": False,
        },
        "runtime_hygiene": {"schema_version": 1, "status": "passed", "finding_count": 0, "findings": []},
        "search": {
            "cluster": {
                "aliases": {
                    "entities": ["pharma-entities-v2-hybrid-20260719"],
                    "evidence": ["pharma-evidence-v2-hybrid-20260719"],
                    "knowledge": ["pharma-knowledge-v2-hybrid-20260719"],
                },
                "available": True,
                "cluster_name": "pharma-search",
                "cluster_status": "green",
                "error": None,
                "version": "3.7.0",
            },
            "deliveries": {"dead": 0, "processing": 0, "retry": 0, "succeeded": 2},
        },
        "hybrid_search": {
            "status": "passed",
            "protocol": "OpenSearch 3.x native hybrid query and normalization pipeline",
            "index_schema_version": 2,
            "embedding_fixture": "deterministic-controlled-test-vector",
            "production_embedding_model_verified": False,
        },
        "duration_seconds": 14,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_database_acceptance_evidence_requires_authority_rls_and_projection_health(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _database_acceptance_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "database", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("migration_drift", "version or migration"),
        ("rls_forged", "tenant RLS"),
        ("rls_signed_negative", "tenant RLS"),
        ("hygiene_finding", "runtime hygiene"),
        ("cluster_red", "cluster evidence"),
        ("alias_drift", "alias is invalid"),
        ("delivery_retry", "delivery queue"),
        ("embedding_overclaim", "hybrid-search"),
        ("zero_duration", "duration"),
    ],
)
def test_database_acceptance_evidence_rejects_authority_or_projection_gaps(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _database_acceptance_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "migration_drift":
        database = report["database"]
        assert isinstance(database, dict)
        database["migration_drift"] = True
    elif mutation == "rls_forged":
        rls = report["rls"]
        assert isinstance(rls, dict)
        rls["forged_context_rows"] = 1
    elif mutation == "rls_signed_negative":
        rls = report["rls"]
        assert isinstance(rls, dict)
        rls["signed_context_rows"] = -1
    elif mutation == "hygiene_finding":
        report["runtime_hygiene"] = {
            "schema_version": 1,
            "status": "failed",
            "finding_count": 1,
            "findings": ["fixture"],
        }
    elif mutation == "cluster_red":
        search = report["search"]
        assert isinstance(search, dict)
        cluster = search["cluster"]
        assert isinstance(cluster, dict)
        cluster["cluster_status"] = "red"
    elif mutation == "alias_drift":
        search = report["search"]
        assert isinstance(search, dict)
        cluster = search["cluster"]
        assert isinstance(cluster, dict)
        aliases = cluster["aliases"]
        assert isinstance(aliases, dict)
        aliases["entities"] = ["wrong-index"]
    elif mutation == "delivery_retry":
        search = report["search"]
        assert isinstance(search, dict)
        deliveries = search["deliveries"]
        assert isinstance(deliveries, dict)
        deliveries["retry"] = 1
    elif mutation == "embedding_overclaim":
        hybrid = report["hybrid_search"]
        assert isinstance(hybrid, dict)
        hybrid["production_embedding_model_verified"] = True
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "database", statement, policy=policy)


def _observability_acceptance_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "schema": release_evidence.OBSERVABILITY_ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "credentials_recorded": False,
        "collector_protocol": "OTLP-gRPC",
        "observed_metrics": ["pharma.mcp.commercial.calls", "pharma.mcp.commercial.duration"],
        "contract": {"services": 9, "objectives": 9, "alerts": 9},
        "commercial_probe": {
            "requests": 4,
            "unique_settlements": 4,
            "active_reservations_after": 0,
            "p95_ms": 150.0,
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_observability_evidence_requires_billed_metrics_at_the_collector(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _observability_acceptance_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "operations_contract", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("missing_metric", "metric inventory"),
        ("contract_count", "contract inventory"),
        ("settlement_gap", "OTLP probe"),
        ("reservation_leak", "OTLP probe"),
        ("latency_failure", "OTLP probe"),
    ],
)
def test_observability_evidence_rejects_contract_or_telemetry_gaps(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _observability_acceptance_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "missing_metric":
        report["observed_metrics"] = ["pharma.mcp.commercial.calls"]
    elif mutation == "contract_count":
        report["contract"] = {"services": 8, "objectives": 9, "alerts": 9}
    else:
        probe = report["commercial_probe"]
        assert isinstance(probe, dict)
        if mutation == "settlement_gap":
            probe["unique_settlements"] = 3
        elif mutation == "reservation_leak":
            probe["active_reservations_after"] = 1
        else:
            probe["p95_ms"] = 2001.0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "operations_contract", statement, policy=policy)


def _parser_sandbox_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    documents = [
        {
            "suffix": suffix,
            "parser_name": contract[0],
            "parser_version": contract[1],
            "metadata_keys": ["record_count"],
            "text_sha256": format(index, "064x"),
        }
        for index, (suffix, contract) in enumerate(release_evidence.PARSER_DOCUMENT_CONTRACTS.items(), start=1)
    ]
    report: dict[str, object] = {
        "schema": release_evidence.PARSER_SANDBOX_SCHEMA,
        "schema_version": 3,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-isolated-parser",
        "production_claim": False,
        "credentials_recorded": False,
        "parser_backend": "service",
        "document_count": 11,
        "documents": documents,
        "unauthorized_status": 401,
        "digest_mismatch_status": 400,
        "duration_seconds": 16,
        "infrastructure": {
            "capabilities_dropped": ["ALL"],
            "memory_limit_bytes": 3 * 1024**3,
            "nano_cpus": 2_000_000_000,
            "network_internal": True,
            "network_member_roles": ["parser", "worker"],
            "parser_secret_scope": [
                "PARSER_SERVICE_HOST",
                "PARSER_SERVICE_LIMIT_CONCURRENCY",
                "PARSER_SERVICE_MAX_CONCURRENT_PARSES",
                "PARSER_SERVICE_MAX_FILE_BYTES",
                "PARSER_SERVICE_MAX_TEXT_CHARS",
                "PARSER_SERVICE_PARSER_CPU_SECONDS",
                "PARSER_SERVICE_PARSER_MEMORY_BYTES",
                "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS",
                "PARSER_SERVICE_PORT",
                "PARSER_SERVICE_TOKEN",
            ],
            "pids_limit": 64,
            "read_only_root_filesystem": True,
        },
        "capacity": {
            "schema_version": 1,
            "generated_at": generated_at,
            "status": "passed",
            "production_claim": False,
            "max_concurrent_parses": 1,
            "held_request_status": 200,
            "saturated_request_status": 429,
            "saturated_error_code": "parser_capacity_exhausted",
            "retry_after_seconds": "1",
            "recovery_request_status": 200,
            "ready_after_status": 200,
        },
        "timeout_recovery": {
            "schema_version": 1,
            "generated_at": generated_at,
            "status": "passed",
            "production_claim": False,
            "timeout_observed": True,
            "child_processes_after_timeout": 0,
            "recovery_parser_name": "text",
            "recovery_text_sha256": "f" * 64,
            "duration_seconds": 0.25,
        },
        "adversarial_corpus": {
            "schema_version": 1,
            "generated_at": generated_at,
            "status": "passed",
            "production_claim": False,
            "case_count": len(release_evidence.PARSER_ADVERSARIAL_CASE_CONTRACTS),
            "cases": [
                {
                    "name": name,
                    "suffix": suffix,
                    "status": 422,
                    "error_code": "document_parse_rejected",
                }
                for name, suffix in release_evidence.PARSER_ADVERSARIAL_CASE_CONTRACTS
            ],
            "recovery_status": 200,
            "ready_after_status": 200,
        },
        "mtls": {
            "schema_version": 1,
            "status": "passed",
            "generated_at": generated_at,
            "production_claim": False,
            "mutual_tls": True,
            "valid_client_parse": True,
            "no_client_certificate_rejected": True,
            "rogue_client_rejected": True,
            "untrusted_server_rejected": True,
            "client_certificate_sha256": "d" * 64,
            "server_certificate_sha256": "e" * 64,
            "duration_seconds": 1.25,
        },
        "outbound_network_blocked": True,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_parser_sandbox_evidence_requires_real_formats_container_isolation_and_mtls(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _parser_sandbox_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "parser_sandbox", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("missing_document", "document inventory"),
        ("parser_drift", "document contract"),
        ("bad_digest", "document contract"),
        ("network_enabled", "scope or status"),
        ("capability_added", "container isolation"),
        ("secret_scope", "container isolation"),
        ("capacity_not_rejected", "capacity and recovery"),
        ("timeout_child_leak", "timeout cleanup and recovery"),
        ("corpus_case_accepted", "adversarial corpus"),
        ("rogue_client", "mutual TLS"),
        ("bad_certificate", "certificate digests"),
        ("zero_duration", "duration"),
    ],
)
def test_parser_sandbox_evidence_rejects_format_or_isolation_gaps(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _parser_sandbox_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation == "missing_document":
        documents = report["documents"]
        assert isinstance(documents, list)
        documents.pop()
    elif mutation in {"parser_drift", "bad_digest"}:
        documents = report["documents"]
        assert isinstance(documents, list)
        document = documents[0]
        assert isinstance(document, dict)
        document["parser_version" if mutation == "parser_drift" else "text_sha256"] = "invalid"
    elif mutation == "network_enabled":
        report["outbound_network_blocked"] = False
    elif mutation in {"capability_added", "secret_scope"}:
        infrastructure = report["infrastructure"]
        assert isinstance(infrastructure, dict)
        if mutation == "capability_added":
            infrastructure["capabilities_dropped"] = []
        else:
            scope = infrastructure["parser_secret_scope"]
            assert isinstance(scope, list)
            scope.pop()
    elif mutation == "capacity_not_rejected":
        capacity = report["capacity"]
        assert isinstance(capacity, dict)
        capacity["saturated_request_status"] = 200
    elif mutation == "timeout_child_leak":
        timeout_recovery = report["timeout_recovery"]
        assert isinstance(timeout_recovery, dict)
        timeout_recovery["child_processes_after_timeout"] = 1
    elif mutation == "corpus_case_accepted":
        adversarial_corpus = report["adversarial_corpus"]
        assert isinstance(adversarial_corpus, dict)
        cases = adversarial_corpus["cases"]
        assert isinstance(cases, list)
        case = cases[0]
        assert isinstance(case, dict)
        case["status"] = 200
    elif mutation == "rogue_client":
        mtls = report["mtls"]
        assert isinstance(mtls, dict)
        mtls["rogue_client_rejected"] = False
    elif mutation == "bad_certificate":
        mtls = report["mtls"]
        assert isinstance(mtls, dict)
        mtls["client_certificate_sha256"] = "invalid"
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "parser_sandbox", statement, policy=policy)


def _ocr_acceptance_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    detection_digest = "a" * 64
    recognition_digest = "b" * 64
    metadata = {
        "format": "OCR text",
        "locator_scheme": "page-region-v1",
        "page_count": 1,
        "line_count": 2,
        "discarded_line_count": 0,
        "mean_confidence": 0.99,
        "minimum_confidence": 0.98,
        "detection_model": "PP-OCRv5_server_det",
        "recognition_model": "PP-OCRv5_server_rec",
        "detection_model_sha256": detection_digest,
        "recognition_model_sha256": recognition_digest,
        "paddlepaddle_version": "3.3.1",
    }
    samples = {
        filename: {
            "source_sha256": source_character * 64,
            "text_sha256": text_character * 64,
            "recognized_text": "EGFR 靶点 IC50 12 nM 临床二期 Clinical Phase 2",
            "metadata": dict(metadata),
            "parser_name": "paddleocr",
            "parser_version": "3.5.0",
        }
        for filename, source_character, text_character in (("scan.png", "c", "e"), ("scan.pdf", "d", "f"))
    }
    report: dict[str, object] = {
        "schema": release_evidence.OCR_ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "category": "ocr_acceptance",
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl-real-pp-ocr",
        "production_claim": False,
        "credentials_recorded": False,
        "real_model": True,
        "real_http": True,
        "typed_parser_fallback": True,
        "protocol_version": 1,
        "runtime": {"paddleocr": "3.5.0", "paddlepaddle": "3.3.1"},
        "model_digests": {
            "PP-OCRv5_server_det": detection_digest,
            "PP-OCRv5_server_rec": recognition_digest,
        },
        "required_fragments": list(release_evidence.OCR_ACCEPTANCE_FRAGMENTS),
        "samples": samples,
        "elapsed_seconds": 27.5,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_ocr_evidence_requires_real_models_http_fallback_and_provenance(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _ocr_acceptance_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "ocr", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("fake_model", "scope or status"),
        ("runtime_drift", "runtime version"),
        ("bad_model_digest", "model digest"),
        ("missing_sample", "sample inventory"),
        ("missing_fragment", "sample result"),
        ("wrong_locator", "provenance metadata"),
        ("metadata_digest_mismatch", "provenance metadata"),
        ("zero_duration", "duration"),
    ],
)
def test_ocr_evidence_rejects_unreal_or_untraceable_results(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _ocr_acceptance_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "fake_model":
        report["real_model"] = False
    elif mutation == "runtime_drift":
        report["runtime"] = {"paddleocr": "3.4.0", "paddlepaddle": "3.3.1"}
    elif mutation == "bad_model_digest":
        model_digests = report["model_digests"]
        assert isinstance(model_digests, dict)
        model_digests["PP-OCRv5_server_det"] = "invalid"
    elif mutation == "missing_sample":
        samples = report["samples"]
        assert isinstance(samples, dict)
        samples.pop("scan.pdf")
    elif mutation in {"missing_fragment", "wrong_locator", "metadata_digest_mismatch"}:
        samples = report["samples"]
        assert isinstance(samples, dict)
        sample = samples["scan.png"]
        assert isinstance(sample, dict)
        if mutation == "missing_fragment":
            sample["recognized_text"] = "EGFR 靶点 IC50"
        else:
            metadata = sample["metadata"]
            assert isinstance(metadata, dict)
            if mutation == "wrong_locator":
                metadata["locator_scheme"] = "page-only"
            else:
                metadata["recognition_model_sha256"] = "e" * 64
    else:
        report["elapsed_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "ocr", statement, policy=policy)


def _runtime_acceptance_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC).isoformat()
    api_image_id = "sha256:" + "a" * 64
    postgres_image_id = "sha256:" + "b" * 64
    report: dict[str, object] = {
        "schema": release_evidence.RUNTIME_ACCEPTANCE_SCHEMA,
        "schema_version": 3,
        "generated_at": generated_at,
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "credentials_recorded": False,
        "compose_profile": "compose+dev+telemetry",
        "services": [
            {
                "service": service,
                "state": "running",
                "health": "healthy",
                "image_id": (
                    api_image_id
                    if service in release_evidence.RUNTIME_APPLICATION_SERVICES
                    else postgres_image_id
                    if service == "postgres"
                    else "sha256:" + "c" * 64
                ),
            }
            for service in release_evidence.RUNTIME_SERVICES
        ],
        "entrypoints": {
            "web": {
                "url": "http://127.0.0.1:18380",
                "liveness": "passed",
                "readiness": "passed",
                "workbenches": {
                    "research": {
                        "path": "/workspace/research",
                        "get_status": 200,
                        "head_status": 200,
                        "content_type": "text/html",
                        "security_headers": "passed",
                        "spa_shell": "passed",
                        "entry_document": "research.html",
                        "workbench_marker": "research",
                        "document_sha256": "1" * 64,
                    },
                    "internal": {
                        "path": "/workspace/internal",
                        "get_status": 200,
                        "head_status": 200,
                        "content_type": "text/html",
                        "security_headers": "passed",
                        "spa_shell": "passed",
                        "entry_document": "internal.html",
                        "workbench_marker": "internal",
                        "document_sha256": "2" * 64,
                    },
                },
            },
            "mcp": {"url": "http://127.0.0.1:18390/mcp", "unauthenticated_status": 401},
            "parser": {"backend": "service", "readiness": "passed"},
        },
        "database": {
            "alembic_head": "5d7e1a3c9b24",
            "postgresql_version": "18.4 (Debian 18.4-1.pgdg13+1)",
            "rdkit_version": "4.8.0",
        },
        "search": {
            "cluster": {
                "aliases": {
                    "entities": ["pharma-entities-v2-hybrid-20260719"],
                    "evidence": ["pharma-evidence-v2-hybrid-20260719"],
                    "knowledge": ["pharma-knowledge-v2-hybrid-20260719"],
                },
                "available": True,
                "cluster_name": "pharma-search",
                "cluster_status": "green",
                "error": None,
                "version": "3.7.0",
            },
            "deliveries": {"dead": 0, "processing": 0, "retry": 0, "succeeded": 2},
        },
        "runtime_hygiene": {"schema_version": 1, "status": "passed", "finding_count": 0, "findings": []},
        "main_runtime_modified": False,
        "duration_seconds": 14,
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    statement: dict[str, object] = {
        "generated_at": generated_at,
        "attachments": [{"path": "report.json"}],
        "subject": {
            "targets": {
                "api": f"pharma-intelligence-api@{api_image_id}",
                "postgres": f"pharma-postgres-rdkit@{postgres_image_id}",
            }
        },
    }
    return tmp_path / "gate-statement.json", statement, report, policy


def test_runtime_evidence_requires_all_services_entries_and_authorities(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _runtime_acceptance_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "runtime", statement, policy=policy)


def test_runtime_evidence_keeps_historical_v1_reports_verifiable(tmp_path: Path) -> None:
    statement_path, statement, report, policy = _runtime_acceptance_statement(tmp_path)
    report["schema"] = release_evidence.RUNTIME_ACCEPTANCE_SCHEMA_V1
    report["schema_version"] = 1
    entrypoints = report["entrypoints"]
    assert isinstance(entrypoints, dict)
    web = entrypoints["web"]
    assert isinstance(web, dict)
    web.pop("workbenches")
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    _validate_specialized_evidence(statement_path, "runtime", statement, policy=policy)


def test_runtime_evidence_keeps_historical_v2_reports_verifiable(tmp_path: Path) -> None:
    statement_path, statement, report, policy = _runtime_acceptance_statement(tmp_path)
    report["schema"] = release_evidence.RUNTIME_ACCEPTANCE_SCHEMA_V2
    report["schema_version"] = 2
    entrypoints = report["entrypoints"]
    assert isinstance(entrypoints, dict)
    web = entrypoints["web"]
    assert isinstance(web, dict)
    workbenches = web["workbenches"]
    assert isinstance(workbenches, dict)
    for workbench in workbenches.values():
        assert isinstance(workbench, dict)
        workbench.pop("entry_document")
        workbench.pop("workbench_marker")
        workbench.pop("document_sha256")
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    _validate_specialized_evidence(statement_path, "runtime", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("extra_field", "scope or status"),
        ("missing_service", "service inventory"),
        ("unhealthy_service", "not healthy"),
        ("unconfigured_worker_health", "not healthy"),
        ("stale_application_image", "security-scanned release images"),
        ("stale_postgres_image", "security-scanned release images"),
        ("open_mcp", "entrypoint boundary"),
        ("missing_workbench", "entrypoint boundary"),
        ("workbench_head_failure", "entrypoint boundary"),
        ("workbench_marker_swap", "entrypoint boundary"),
        ("shared_workbench_document", "not distinct"),
        ("migration_drift", "database authority"),
        ("search_red", "OpenSearch projection"),
        ("delivery_retry", "OpenSearch projection"),
        ("hygiene_finding", "data hygiene"),
        ("modified_runtime", "scope or status"),
        ("zero_duration", "duration"),
    ],
)
def test_runtime_evidence_rejects_unhealthy_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _runtime_acceptance_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "extra_field":
        report["uncontracted"] = True
    elif mutation in {"missing_service", "unhealthy_service", "unconfigured_worker_health"}:
        services = report["services"]
        assert isinstance(services, list)
        if mutation == "missing_service":
            services.pop()
        elif mutation == "unconfigured_worker_health":
            service = next(item for item in services if isinstance(item, dict) and item.get("service") == "worker")
            service["health"] = "none"
        else:
            service = services[0]
            assert isinstance(service, dict)
            service["health"] = "unhealthy"
    elif mutation in {"stale_application_image", "stale_postgres_image"}:
        services = report["services"]
        assert isinstance(services, list)
        target_name = "api" if mutation == "stale_application_image" else "postgres"
        service = next(item for item in services if isinstance(item, dict) and item.get("service") == target_name)
        service["image_id"] = "sha256:" + "d" * 64
    elif mutation == "open_mcp":
        entrypoints = report["entrypoints"]
        assert isinstance(entrypoints, dict)
        mcp = entrypoints["mcp"]
        assert isinstance(mcp, dict)
        mcp["unauthenticated_status"] = 200
    elif mutation in {
        "missing_workbench",
        "workbench_head_failure",
        "workbench_marker_swap",
        "shared_workbench_document",
    }:
        entrypoints = report["entrypoints"]
        assert isinstance(entrypoints, dict)
        web = entrypoints["web"]
        assert isinstance(web, dict)
        workbenches = web["workbenches"]
        assert isinstance(workbenches, dict)
        if mutation == "missing_workbench":
            workbenches.pop("internal")
        elif mutation == "workbench_head_failure":
            research = workbenches["research"]
            assert isinstance(research, dict)
            research["head_status"] = 404
        elif mutation == "workbench_marker_swap":
            internal = workbenches["internal"]
            assert isinstance(internal, dict)
            internal["workbench_marker"] = "research"
        else:
            research = workbenches["research"]
            internal = workbenches["internal"]
            assert isinstance(research, dict)
            assert isinstance(internal, dict)
            internal["document_sha256"] = research["document_sha256"]
    elif mutation == "migration_drift":
        database = report["database"]
        assert isinstance(database, dict)
        database["alembic_head"] = "000000000000"
    elif mutation in {"search_red", "delivery_retry"}:
        search = report["search"]
        assert isinstance(search, dict)
        if mutation == "search_red":
            cluster = search["cluster"]
            assert isinstance(cluster, dict)
            cluster["cluster_status"] = "red"
        else:
            deliveries = search["deliveries"]
            assert isinstance(deliveries, dict)
            deliveries["retry"] = 1
    elif mutation == "hygiene_finding":
        report["runtime_hygiene"] = {
            "schema_version": 1,
            "status": "failed",
            "finding_count": 1,
            "findings": ["fixture"],
        }
    elif mutation == "modified_runtime":
        report["main_runtime_modified"] = True
    else:
        report["duration_seconds"] = 0
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "runtime", statement, policy=policy)


def _clean_source_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC)
    subject = {
        "git_commit": "a" * 40,
        "source_file_count": 359,
        "source_tree_sha256": "b" * 64,
        "targets": {
            "api": "example.invalid/api@sha256:" + "c" * 64,
            "ocr": "example.invalid/ocr@sha256:" + "d" * 64,
        },
    }
    statement: dict[str, object] = {
        "generated_at": generated_at.isoformat(),
        "subject": subject,
        "attachments": [{"path": "report.json"}],
    }
    report: dict[str, object] = {
        "schema": release_evidence.CLEAN_SOURCE_SCHEMA,
        "schema_version": 1,
        "status": "passed",
        "generated_at": generated_at.isoformat(),
        "subject": {
            "git_commit": subject["git_commit"],
            "source_file_count": subject["source_file_count"],
            "source_tree_sha256": subject["source_tree_sha256"],
        },
        "checks": {name: True for name in release_evidence.CLEAN_SOURCE_CHECKS},
        "application_image_digest": "sha256:" + "d" * 64,
        "application_image_user": "app",
        "commands": [
            {"label": label, "duration_ms": index + 1, "exit_code": 0}
            for index, label in enumerate(release_evidence.CLEAN_SOURCE_COMMANDS)
        ],
    }
    statement_path = tmp_path / "gate-statement.json"
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return statement_path, statement, report, policy


def test_clean_source_evidence_requires_the_full_reproducibility_contract(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _clean_source_statement(tmp_path)

    assert "historical_runtime_evidence_excluded" in release_evidence.CLEAN_SOURCE_CHECKS
    assert "portable_source_paths" in release_evidence.CLEAN_SOURCE_CHECKS
    _validate_specialized_evidence(statement_path, "source_reproducibility", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong_subject", "release source"),
        ("failed_check", "every contracted check"),
        ("root_image", "non-root image"),
        ("missing_command", "command inventory"),
    ],
)
def test_clean_source_evidence_rejects_incomplete_or_unbound_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _clean_source_statement(tmp_path)
    if mutation == "wrong_subject":
        report["subject"] = {"git_commit": "f" * 40}
    elif mutation == "failed_check":
        checks = report["checks"]
        assert isinstance(checks, dict)
        checks["runtime_image_smoke"] = False
    elif mutation == "root_image":
        report["application_image_user"] = "root"
    else:
        commands = report["commands"]
        assert isinstance(commands, list)
        commands.pop()
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "source_reproducibility", statement, policy=policy)


def _performance_baseline_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    generated_at = datetime.now(UTC)
    statement: dict[str, object] = {
        "generated_at": generated_at.isoformat(),
        "attachments": [{"path": "report.json"}],
    }
    phase = {
        "requested": 10,
        "completed": 10,
        "failed": 0,
        "web_completed": 5,
        "mcp_completed": 5,
        "unique_mcp_settlements": 5,
        "errors": [],
    }
    report: dict[str, object] = {
        "schema": release_evidence.PERFORMANCE_BASELINE_SCHEMA,
        "schema_version": 1,
        "status": "passed",
        "production_claim": False,
        "environment_kind": "local-controlled-baseline",
        "generated_at": generated_at.isoformat(),
        "credentials_recorded": False,
        "temporary_users_after": 0,
        "temporary_human_role": "viewer",
        "assertions": {name: True for name in release_evidence.PERFORMANCE_BASELINE_ASSERTIONS},
        "phases": [
            {**phase, "name": "sustained", "concurrency": 4},
            {**phase, "name": "peak", "concurrency": 8},
        ],
        "aggregate": {
            "web_completed": 10,
            "mcp_completed": 10,
            "settlement_delta": 10,
            "charged_units_delta": "10.00000000",
            "consumed_units_delta": "10.00000000",
            "active_reservations_after_load": 0,
            "active_reservations_final": 0,
            "web_latency_ms": {"p95": 100.0},
            "mcp_latency_ms": {"p95": 200.0},
        },
        "thresholds": {"web_p95_ms": 800.0, "mcp_p95_ms": 2000.0},
        "concurrent_idempotency": {
            "settlement_delta": 1,
            "unique_settlements": 1,
            "active_reservations_after": 0,
            "assertions": {name: True for name in release_evidence.PERFORMANCE_RACE_ASSERTIONS},
        },
        "failure_injection": {"assertions": {"timeout_terminal": True}},
        "coverage": {
            "long_running": False,
            "target_infrastructure_faults": False,
            "production_approvals": False,
        },
        "production_gaps": ["long-running", "managed dependencies", "approvals"],
    }
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return tmp_path / "gate-statement.json", statement, report, policy


def test_local_performance_baseline_requires_mixed_load_and_commercial_integrity(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _performance_baseline_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "performance_baseline", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("production_claim", "scope or status"),
        ("failed_assertion", "mixed-load assertion"),
        ("missing_phase", "phase inventory"),
        ("duplicate_settlement", "idempotency evidence"),
        ("hide_gap", "production boundary"),
    ],
)
def test_local_performance_baseline_rejects_incomplete_or_overclaimed_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, report, policy = _performance_baseline_statement(tmp_path)
    if mutation == "production_claim":
        report["production_claim"] = True
    elif mutation == "failed_assertion":
        assertions = report["assertions"]
        assert isinstance(assertions, dict)
        assertions["mcp_p95_within_local_threshold"] = False
    elif mutation == "missing_phase":
        report["phases"] = []
    elif mutation == "duplicate_settlement":
        race = report["concurrent_idempotency"]
        assert isinstance(race, dict)
        race["settlement_delta"] = 2
    else:
        coverage = report["coverage"]
        assert isinstance(coverage, dict)
        coverage["long_running"] = True
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "performance_baseline", statement, policy=policy)


def _valid_production_topology_report(
    subject: dict[str, object], tested_at: datetime, *, profile: str = "core_commercial"
) -> dict[str, object]:
    versions = {
        "python": "3.13.14",
        "postgresql": "18.4",
        "rdkit": "2026.03.3",
        "opensearch": "3.7.0",
        "object_storage": "S3-2006-03-01",
        "temporal": "1.29.6",
        "valkey": "9.0.1",
        "identity": "26.2.5",
        "secrets": "2.4.0",
        "gateway": "1.6.0",
        "kubernetes": "1.34.1",
        "observability": "1.0.0",
    }
    replicas = {
        "python": 3,
        "postgresql": 3,
        "rdkit": 3,
        "opensearch": 3,
        "object_storage": 3,
        "temporal": 3,
        "valkey": 3,
        "identity": 2,
        "secrets": 3,
        "gateway": 3,
        "kubernetes": 6,
        "observability": 3,
    }
    event_projection = (
        {
            "mode": "transactional_outbox",
            "kafka_version": None,
            "debezium_version": None,
            "clickhouse_enabled": False,
            "iceberg_enabled": False,
        }
        if profile == "core_commercial"
        else {
            "mode": "kafka_cdc",
            "kafka_version": "4.1.0",
            "debezium_version": "3.4.0",
            "clickhouse_enabled": True,
            "iceberg_enabled": True,
        }
    )
    return {
        "schema": release_evidence.PRODUCTION_TOPOLOGY_SCHEMA,
        "schema_version": 1,
        "status": "passed",
        "environment_kind": "preproduction",
        "environment_id": "preprod-us-east-1",
        "tested_at": tested_at.isoformat(),
        "subject": subject,
        "profile": profile,
        "entrypoints": {
            "public_entry_count": 2,
            "web_url": "https://portal.pharma-assurance.net",
            "mcp_url": "https://mcp.pharma-assurance.net",
        },
        "components": {
            name: {
                "version": version,
                "deployment_reference": f"DEPLOY-{name.upper()}-2026-07",
                "replicas": replicas[name],
                "managed_or_ha": True,
            }
            for name, version in versions.items()
        },
        "event_projection": event_projection,
        "authority": {
            "canonical_store": "postgresql",
            "chemical_authority": "postgresql_rdkit",
            "search_role": "derived_projection",
            "object_role": "immutable_evidence",
            "metering_authority": "postgresql_append_only_ledger",
            "web_direct_database_access": False,
            "mcp_direct_database_access": False,
        },
        "resilience": {
            "multi_az": True,
            "postgres_pitr": True,
            "object_versioning": True,
            "object_lock": True,
            "opensearch_replicas": True,
            "temporal_ha": True,
            "valkey_ha": True,
            "kubernetes_pdb_hpa": True,
            "gitops_rollback": True,
            "central_observability": True,
        },
        "migration": {
            "postgresql16_critical_path": False,
            "postgresql17_adr_reference": None,
            "ragflow_critical_path": False,
            "ragflow_exit_plan_reference": "ARCH-RAGFLOW-EXIT-2026-07",
            "ragflow_adapter_removal_criteria": "OpenSearch evidence projection and parser acceptance approved",
            "legacy_profile_isolated": True,
        },
        "references": {
            "architecture_approval": "ARCH-APPROVAL-2026-07",
            "deployment_inventory": "DEPLOY-INVENTORY-2026-07",
            "version_matrix": "VERSION-MATRIX-2026-07",
            "ragflow_exit_plan": "ARCH-RAGFLOW-EXIT-2026-07",
        },
    }


def _valid_production_topology_live_probe(
    subject: dict[str, object],
    tested_at: datetime,
    topology_path: Path,
) -> dict[str, object]:
    targets = subject["targets"]
    assert isinstance(targets, dict)
    application_image = str(targets["api"])
    ocr_image = str(targets["ocr"])
    hpa_workloads = release_evidence.PRODUCTION_TOPOLOGY_HPA_WORKLOADS
    return {
        "schema": release_evidence.PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
        "schema_version": 1,
        "status": "passed",
        "environment_kind": "preproduction",
        "environment_id": "preprod-us-east-1",
        "tested_at": tested_at.isoformat(),
        "subject": subject,
        "topology_report_sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
        "kube_context_sha256": "d" * 64,
        "namespace": "pharma-intelligence",
        "namespace_uid": "11111111-1111-4111-8111-111111111111",
        "kubernetes": {
            "server_version": "1.34.1",
            "ready_schedulable_nodes": 6,
            "availability_zones": ["us-east-1a", "us-east-1b", "us-east-1c"],
            "node_architectures": ["amd64"],
        },
        "workloads": [
            {
                "name": name,
                "kind": "Deployment",
                "desired_replicas": 3,
                "ready_replicas": 3,
                "available_replicas": 3,
                "generation": 7,
                "observed_generation": 7,
                "image_digests": [ocr_image if name == "pharma-ocr" else application_image],
                "pdb_present": True,
                "hpa_present": name in hpa_workloads,
            }
            for name in sorted(release_evidence.PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS)
        ],
        "gateway": {
            "name": "pharma-public",
            "programmed": True,
            "listener_hosts": ["mcp.pharma-assurance.net", "portal.pharma-assurance.net"],
            "route_hosts": ["mcp.pharma-assurance.net", "portal.pharma-assurance.net"],
        },
        "network_policy": {
            "count": 12,
            "default_deny_ingress": True,
            "default_deny_egress": True,
        },
        "endpoints": {
            "web": {
                "url": "https://portal.pharma-assurance.net",
                "status_code": 200,
                "tls_version": "TLSv1.3",
                "certificate_sha256": "e" * 64,
                "hsts": True,
                "unauthenticated_rejected": None,
            },
            "mcp": {
                "url": "https://mcp.pharma-assurance.net",
                "status_code": 401,
                "tls_version": "TLSv1.3",
                "certificate_sha256": "f" * 64,
                "hsts": True,
                "unauthenticated_rejected": True,
            },
        },
        "credentials_recorded": False,
    }


def _production_gate_statement(
    tmp_path: Path,
    category: str,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")
    contract = policy.production_contracts[category]
    statement_path = tmp_path / "gate-statement.json"
    generated_at = datetime.now(UTC)
    subject = {
        "git_commit": "a" * 40,
        "source_file_count": 354,
        "source_tree_sha256": "b" * 64,
        "targets": {
            "api": "example.invalid/api@sha256:" + "c" * 64,
            "ocr": "example.invalid/ocr@sha256:" + "d" * 64,
        },
    }
    statement: dict[str, object] = {
        "generated_at": generated_at.isoformat(),
        "subject": subject,
        "attachments": [],
    }
    artifact_documents: list[dict[str, object]] = []
    for index in range(contract.minimum_artifacts):
        path = f"artifacts/{category}-report-{index + 1}.json"
        artifact_path = tmp_path / path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps({"status": "passed", "sequence": index + 1}), encoding="utf-8")
        artifact_documents.append(
            {
                "name": f"{category}-report-{index + 1}",
                "path": path,
                "size": artifact_path.stat().st_size,
                "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                "reference": f"EVIDENCE-{category.upper()}-{index + 1}",
            }
        )
    if category == "production_topology":
        replaced_artifact_path = tmp_path / str(artifact_documents[0]["path"])
        replaced_artifact_path.unlink()
        topology_path = tmp_path / release_evidence.PRODUCTION_TOPOLOGY_REPORT
        topology_path.write_text(json.dumps(_valid_production_topology_report(subject, generated_at)), encoding="utf-8")
        artifact_documents[0] = {
            "name": "production-topology-report",
            "path": release_evidence.PRODUCTION_TOPOLOGY_REPORT,
            "size": topology_path.stat().st_size,
            "sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
            "reference": "EVIDENCE-PRODUCTION-TOPOLOGY-DETAIL",
        }
        replaced_probe_artifact = tmp_path / str(artifact_documents[1]["path"])
        replaced_probe_artifact.unlink()
        probe_path = tmp_path / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
        probe_path.write_text(
            json.dumps(_valid_production_topology_live_probe(subject, generated_at, topology_path)),
            encoding="utf-8",
        )
        artifact_documents[1] = {
            "name": "production-topology-live-probe",
            "path": release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT,
            "size": probe_path.stat().st_size,
            "sha256": hashlib.sha256(probe_path.read_bytes()).hexdigest(),
            "reference": "EVIDENCE-PRODUCTION-TOPOLOGY-LIVE-PROBE",
        }
    approval_documents: list[dict[str, object]] = []
    for role in sorted(contract.approval_roles):
        path = f"approvals/{role}.json"
        approval_path = tmp_path / path
        approval_path.parent.mkdir(parents=True, exist_ok=True)
        approval_path.write_text(
            json.dumps({"role": role, "decision": "approved", "subject": subject}), encoding="utf-8"
        )
        approval_documents.append(
            {
                "role": role,
                "reference": f"APPROVAL-{role.upper()}",
                "organization": f"Approved-{role}",
                "approved_at": generated_at.isoformat(),
                "artifact_path": path,
                "artifact_size": approval_path.stat().st_size,
                "artifact_sha256": hashlib.sha256(approval_path.read_bytes()).hexdigest(),
            }
        )
    report: dict[str, object] = {
        "schema": "pharma.production-gate-evidence.v2",
        "schema_version": 2,
        "category": category,
        "status": "passed",
        "environment_kind": "preproduction",
        "environment_id": "preprod-us-east-1",
        "tested_at": generated_at.isoformat(),
        "subject": subject,
        "checks": {name: True for name in contract.checks},
        "executor": {
            "organization": "External-Assurance-Provider",
            "team": "Validated-Delivery-Team",
            "independent": contract.require_independent_executor,
        },
        "artifacts": artifact_documents,
        "approvals": approval_documents,
    }
    (tmp_path / contract.report_name).write_text(json.dumps(report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)
    return statement_path, statement, report, policy


def _production_intake_request(
    tmp_path: Path,
    repo: Path,
    *,
    category: str = "performance",
) -> tuple[Path, Path, Path, dict[str, object], release_evidence.EvidencePolicy]:
    root = Path(__file__).parents[1]
    policy_path = root / "deploy" / "release" / "evidence-policy.json"
    policy = load_policy(policy_path)
    contract = policy.production_contracts[category]
    external = tmp_path / "external-evidence"
    external.mkdir()
    artifact_documents: list[dict[str, object]] = []
    for index in range(contract.minimum_artifacts):
        suffix = "" if index == 0 else f"-{index + 1}"
        artifact_source = external / f"{category}-report{suffix}.json"
        artifact_source.write_text(
            json.dumps({"status": "passed", "category": category, "sequence": index + 1}) + "\n",
            encoding="utf-8",
        )
        artifact_documents.append(
            {
                "name": f"approved-{category}-report{suffix}",
                "source_path": str(artifact_source),
                "destination": f"artifacts/{category}-report{suffix}.json",
                "reference": f"EVIDENCE-{category.upper()}-{index + 1}",
            }
        )
    approvals: list[dict[str, object]] = []
    now = datetime.now(UTC).isoformat()
    for role in sorted(contract.approval_roles):
        approval_source = external / f"{role}-approval.json"
        approval_source.write_text(
            json.dumps({"role": role, "decision": "approved", "reference": f"APPROVAL-{role.upper()}"}),
            encoding="utf-8",
        )
        approvals.append(
            {
                "role": role,
                "source_path": str(approval_source),
                "destination": f"approvals/{role}-approval.json",
                "reference": f"APPROVAL-{role.upper()}",
                "organization": "Pharma-Delivery-Organization",
                "approved_at": now,
            }
        )
    request_document: dict[str, object] = {
        "schema": release_evidence.PRODUCTION_INTAKE_SCHEMA,
        "schema_version": 1,
        "category": category,
        "environment_kind": "preproduction",
        "environment_id": "preprod-cn-east-1",
        "tested_at": now,
        "checks": sorted(contract.checks),
        "executor": {
            "organization": "External-Assurance-Provider",
            "team": "Validated-Delivery-Team",
            "independent": contract.require_independent_executor,
        },
        "artifacts": artifact_documents,
        "approvals": approvals,
    }
    request_path = tmp_path / "production-intake.json"
    request_path.write_text(json.dumps(request_document), encoding="utf-8")
    return request_path, policy_path, tmp_path / "registered-performance", request_document, policy


def _validate_production_intake_schema(document: dict[str, object]) -> None:
    schema = json.loads(
        (Path(__file__).parents[1] / "deploy" / "release" / "production-evidence-intake.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


def test_register_production_evidence_atomically_binds_external_files(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    request, policy_path, output, _, policy = _production_intake_request(tmp_path, repo)
    request_document = json.loads(request.read_text(encoding="utf-8"))
    _validate_production_intake_schema(request_document)

    result = register_production_evidence(
        repo=repo,
        policy_path=policy_path,
        security_directory=security,
        request_path=request,
        output=output,
    )

    assert result == {
        "schema_version": 1,
        "status": "registered",
        "category": "performance",
        "statement": str(output / "gate-statement.json"),
        "attachment_count": 4,
        "total_attachment_bytes": result["total_attachment_bytes"],
        "production_claim": False,
    }
    assert isinstance(result["total_attachment_bytes"], int) and result["total_attachment_bytes"] > 0
    statement = json.loads((output / "gate-statement.json").read_text(encoding="utf-8"))
    report = json.loads((output / "production-evidence-report.json").read_text(encoding="utf-8"))
    assert report["subject"] == statement["subject"]
    assert "source_path" not in json.dumps(report)
    assert {item["path"] for item in statement["attachments"]} == {
        "production-evidence-report.json",
        "artifacts/performance-report.json",
        "approvals/platform-approval.json",
        "approvals/product-approval.json",
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in output.rglob("*") if path.is_file())
    _validate_specialized_evidence(
        output / "gate-statement.json",
        "performance",
        statement,
        policy=policy,
    )
    category, validated = _statement_category(
        output / "gate-statement.json",
        policy=policy,
        subject=repository_subject(repo),
        security=validate_security_evidence(security, repository_subject(repo)),
    )
    assert category == "performance"
    assert validated == statement


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_check", "every contracted check"),
        ("missing_approval", "required approval roles"),
        ("path_traversal", "destination path is unsafe"),
        ("local_environment", "local or development"),
        ("reused_source", "cannot reuse one source file"),
        ("repository_source", "outside the source repository"),
        ("empty_source", "must be non-empty"),
        ("approval_before_test", "predates the tested evidence"),
    ],
)
def test_register_production_evidence_rejects_untrusted_intake_atomically(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    request, policy_path, output, document, _ = _production_intake_request(tmp_path, repo)
    checks = document["checks"]
    artifacts = document["artifacts"]
    approvals = document["approvals"]
    assert isinstance(checks, list)
    assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
    assert isinstance(approvals, list) and isinstance(approvals[0], dict)
    if mutation == "missing_check":
        checks.pop()
    elif mutation == "missing_approval":
        approvals.pop()
    elif mutation == "path_traversal":
        artifacts[0]["destination"] = "artifacts/../../escape.json"
    elif mutation == "local_environment":
        document["environment_id"] = "local-development"
    elif mutation == "reused_source":
        approvals[0]["source_path"] = artifacts[0]["source_path"]
    elif mutation == "repository_source":
        artifacts[0]["source_path"] = str(repo / "source.txt")
    elif mutation == "approval_before_test":
        tested_at = datetime.fromisoformat(str(document["tested_at"]))
        approvals[0]["approved_at"] = (tested_at - timedelta(hours=1)).isoformat()
    else:
        empty = tmp_path / "external-evidence" / "empty.json"
        empty.touch()
        artifacts[0]["source_path"] = str(empty)
    request.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=message):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=request,
            output=output,
        )

    assert not output.exists()
    assert not list(tmp_path.glob(f".{output.name}.intake-*"))


def test_register_production_evidence_rejects_symlinks_and_overwrite(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    request, policy_path, output, document, _ = _production_intake_request(tmp_path, repo)
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
    source = Path(str(artifacts[0]["source_path"]))
    link = source.with_name("linked-report.json")
    link.symlink_to(source)
    artifacts[0]["source_path"] = str(link)
    request.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="not symbolic links"):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=request,
            output=output,
        )

    artifacts[0]["source_path"] = str(source)
    request.write_text(json.dumps(document), encoding="utf-8")
    output.mkdir()
    with pytest.raises(ReleaseEvidenceError, match="refusing to overwrite"):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=request,
            output=output,
        )


def test_register_production_evidence_refuses_repository_output(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    request, policy_path, _, _, _ = _production_intake_request(tmp_path, repo)

    with pytest.raises(ReleaseEvidenceError, match="outside the source repository"):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=request,
            output=repo / "production-evidence",
        )


def test_register_production_evidence_refuses_repository_or_oversized_requests(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security = _security(tmp_path, repo)
    request, policy_path, output, document, _ = _production_intake_request(tmp_path, repo)
    repository_request = repo / "production-intake.json"
    repository_request.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="request must be outside"):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=repository_request,
            output=output,
        )

    repository_request.unlink()
    oversized = tmp_path / "oversized-intake.json"
    oversized.write_bytes(b"{" + b" " * release_evidence.MAX_PRODUCTION_INTAKE_BYTES + b"}")
    with pytest.raises(ReleaseEvidenceError, match="no larger than"):
        register_production_evidence(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            request_path=oversized,
            output=output,
        )


def test_production_evidence_requirements_expose_the_authoritative_contract() -> None:
    root = Path(__file__).parents[1]
    policy_path = root / "deploy" / "release" / "evidence-policy.json"
    requirements = production_evidence_requirements(policy_path=policy_path, category="penetration_test")

    assert requirements == {
        "schema": "pharma.production-evidence-requirements.v2",
        "schema_version": 2,
        "category": "penetration_test",
        "max_age_hours": 720,
        "checks": [
            "audit_integrity",
            "cross_tenant",
            "export_controls",
            "findings_closed_or_accepted",
            "injection",
            "privilege_escalation",
        ],
        "approval_roles": ["independent_tester", "security"],
        "minimum_artifacts": 1,
        "require_independent_executor": True,
        "intake_schema": "deploy/release/production-evidence-intake.schema.json",
        "report_schema": "deploy/release/production-evidence-report.schema.json",
        "detail_reports": [],
        "production_claim": False,
    }
    topology_requirements = production_evidence_requirements(policy_path=policy_path, category="production_topology")
    assert topology_requirements["detail_reports"] == [
        {
            "path": release_evidence.PRODUCTION_TOPOLOGY_REPORT,
            "schema": release_evidence.PRODUCTION_TOPOLOGY_SCHEMA,
            "schema_file": "deploy/release/production-topology-report.schema.json",
        },
        {
            "path": release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT,
            "schema": release_evidence.PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
            "schema_file": "deploy/release/production-topology-live-probe.schema.json",
        },
    ]
    with pytest.raises(ReleaseEvidenceError, match="does not accept external production evidence"):
        production_evidence_requirements(policy_path=policy_path, category="quality")


def test_register_production_evidence_supports_mcp_sender_detail_contract(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security_path = _security(tmp_path, repo)
    request, policy_path, output, document, policy = _production_intake_request(
        tmp_path,
        repo,
        category="mcp_sender_constraint",
    )
    subject = repository_subject(repo)
    security = validate_security_evidence(security_path, subject)
    bound_subject = {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": security.targets,
    }
    detail = {
        "schema": release_evidence.MCP_SENDER_CONSTRAINT_SCHEMA,
        "schema_version": 2,
        "status": "passed",
        "environment_kind": document["environment_kind"],
        "environment_id": document["environment_id"],
        "tested_at": document["tested_at"],
        "subject": bound_subject,
        "idp_issuer_url": "https://identity.preprod.vendor.com",
        "resource_server_url": "https://mcp.preprod.customer.com/mcp",
        "clients": [
            {"name": "official-python-sdk", "version": "1.28.1", "dpop_supported": True},
            {"name": "enterprise-agent", "version": "4.2.0", "dpop_supported": True},
        ],
        "checks": {name: True for name in release_evidence.MCP_SENDER_CONSTRAINT_CHECKS},
        "replay_store": {"failure_mode": "fail_closed", "shared": True, "tls": True},
        "references": {
            "gateway_change": "CHG-GATEWAY-1024",
            "idp_change": "CHG-IDP-2048",
            "security_approval": "SEC-APPROVAL-4096",
        },
    }
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list) and len(artifacts) == 2 and isinstance(artifacts[0], dict)
    detail_source = Path(str(artifacts[0]["source_path"]))
    detail_source.write_text(json.dumps(detail), encoding="utf-8")
    artifacts[0]["name"] = "mcp-sender-constraint-protocol-report"
    artifacts[0]["destination"] = release_evidence.MCP_SENDER_CONSTRAINT_REPORT
    artifacts[0]["reference"] = "MCP-DPOP-PREPROD-REPORT"
    _validate_production_intake_schema(document)
    request.write_text(json.dumps(document), encoding="utf-8")

    register_production_evidence(
        repo=repo,
        policy_path=policy_path,
        security_directory=security_path,
        request_path=request,
        output=output,
    )

    statement_path = output / "gate-statement.json"
    assert (output / release_evidence.MCP_SENDER_CONSTRAINT_REPORT).is_file()
    category, _ = _statement_category(
        statement_path,
        policy=policy,
        subject=subject,
        security=security,
    )
    assert category == "mcp_sender_constraint"


def test_register_production_evidence_supports_topology_detail_contract(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    security_path = _security(tmp_path, repo)
    request, policy_path, output, document, policy = _production_intake_request(
        tmp_path,
        repo,
        category="production_topology",
    )
    subject = repository_subject(repo)
    security = validate_security_evidence(security_path, subject)
    bound_subject = {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": security.targets,
    }
    tested_at = datetime.fromisoformat(str(document["tested_at"]))
    detail = _valid_production_topology_report(bound_subject, tested_at)
    detail["environment_kind"] = document["environment_kind"]
    detail["environment_id"] = document["environment_id"]
    artifacts = document["artifacts"]
    assert (
        isinstance(artifacts, list)
        and len(artifacts) == 4
        and isinstance(artifacts[0], dict)
        and isinstance(artifacts[1], dict)
    )
    detail_source = Path(str(artifacts[0]["source_path"]))
    detail_source.write_text(json.dumps(detail), encoding="utf-8")
    artifacts[0]["name"] = "production-topology-detail-report"
    artifacts[0]["destination"] = release_evidence.PRODUCTION_TOPOLOGY_REPORT
    artifacts[0]["reference"] = "TOPOLOGY-PREPROD-REPORT"
    live_detail = _valid_production_topology_live_probe(bound_subject, tested_at, detail_source)
    live_detail["environment_kind"] = document["environment_kind"]
    live_detail["environment_id"] = document["environment_id"]
    live_source = Path(str(artifacts[1]["source_path"]))
    live_source.write_text(json.dumps(live_detail), encoding="utf-8")
    artifacts[1]["name"] = "production-topology-live-probe"
    artifacts[1]["destination"] = release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
    artifacts[1]["reference"] = "TOPOLOGY-PREPROD-LIVE-PROBE"
    _validate_production_intake_schema(document)
    request.write_text(json.dumps(document), encoding="utf-8")

    register_production_evidence(
        repo=repo,
        policy_path=policy_path,
        security_directory=security_path,
        request_path=request,
        output=output,
    )

    statement_path = output / "gate-statement.json"
    assert (output / release_evidence.PRODUCTION_TOPOLOGY_REPORT).is_file()
    assert (output / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT).is_file()
    category, _ = _statement_category(
        statement_path,
        policy=policy,
        subject=subject,
        security=security,
    )
    assert category == "production_topology"


@pytest.mark.parametrize(
    ("category", "destination"),
    [
        ("performance", release_evidence.MCP_SENDER_CONSTRAINT_REPORT),
        ("performance", release_evidence.PRODUCTION_TOPOLOGY_REPORT),
        ("mcp_sender_constraint", release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT),
        ("production_topology", release_evidence.MCP_SENDER_CONSTRAINT_REPORT),
    ],
)
def test_production_intake_schema_rejects_cross_category_detail_reports(
    tmp_path: Path,
    category: str,
    destination: str,
) -> None:
    repo = _repository(tmp_path)
    _, _, _, document, _ = _production_intake_request(tmp_path, repo, category=category)
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
    artifacts[0]["destination"] = destination

    schema = json.loads(
        (Path(__file__).parents[1] / "deploy" / "release" / "production-evidence-intake.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert not Draft202012Validator(schema).is_valid(document)


def _refresh_production_attachments(tmp_path: Path, statement: dict[str, object]) -> None:
    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file() and path.name != "gate-statement.json"
    ]
    statement["attachments"] = [
        {
            "path": path,
            "size": (tmp_path / path).stat().st_size,
            "sha256": hashlib.sha256((tmp_path / path).read_bytes()).hexdigest(),
        }
        for path in paths
    ]


@pytest.mark.parametrize(
    "category",
    [
        "anti_extraction",
        "billing_provider",
        "change_approval",
        "data_licensing",
        "disaster_recovery",
        "external_services",
        "infrastructure_ha_pitr",
        "ingestion",
        "operations_approval",
        "penetration_test",
        "performance",
        "product_uat",
    ],
)
def test_external_production_evidence_requires_contracted_semantics(tmp_path: Path, category: str) -> None:
    statement_path, statement, _, policy = _production_gate_statement(tmp_path, category)

    _validate_specialized_evidence(statement_path, category, statement, policy=policy)


def test_production_evidence_json_schema_matches_runtime_contract() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "deploy" / "release" / "production-evidence-report.schema.json").read_text(encoding="utf-8")
    )
    intake_schema = json.loads(
        (root / "deploy" / "release" / "production-evidence-intake.schema.json").read_text(encoding="utf-8")
    )
    batch_intake_schema = json.loads(
        (root / "deploy" / "release" / "production-evidence-batch-intake.schema.json").read_text(encoding="utf-8")
    )
    batch_manifest_schema = json.loads(
        (root / "deploy" / "release" / "production-evidence-batch-manifest.schema.json").read_text(encoding="utf-8")
    )
    handoff_schema = json.loads(
        (root / "deploy" / "release" / "production-evidence-handoff-manifest.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["schema"]["const"] == release_evidence.PRODUCTION_GATE_SCHEMA
    assert schema["properties"]["schema_version"]["const"] == 2
    assert set(schema["properties"]["artifacts"]["items"]["required"]) == {
        "name",
        "path",
        "size",
        "sha256",
        "reference",
    }
    assert set(schema["properties"]["approvals"]["items"]["required"]) >= {
        "role",
        "artifact_path",
        "artifact_size",
        "artifact_sha256",
    }
    assert schema["properties"]["artifacts"]["items"]["properties"]["size"]["minimum"] == 1
    assert schema["properties"]["approvals"]["items"]["properties"]["artifact_size"]["minimum"] == 1
    assert intake_schema["properties"]["schema"]["const"] == release_evidence.PRODUCTION_INTAKE_SCHEMA
    assert set(intake_schema["required"]) == release_evidence.PRODUCTION_INTAKE_FIELDS
    assert set(intake_schema["properties"]["artifacts"]["items"]["required"]) == (
        release_evidence.PRODUCTION_INTAKE_ARTIFACT_FIELDS
    )
    assert set(intake_schema["properties"]["approvals"]["items"]["required"]) == (
        release_evidence.PRODUCTION_INTAKE_APPROVAL_FIELDS
    )
    assert batch_intake_schema["properties"]["schema"]["const"] == release_evidence.PRODUCTION_BATCH_INTAKE_SCHEMA
    assert set(batch_intake_schema["required"]) == release_evidence.PRODUCTION_BATCH_INTAKE_FIELDS
    assert set(batch_intake_schema["properties"]["requests"]["items"]["required"]) == (
        release_evidence.PRODUCTION_BATCH_ENTRY_FIELDS
    )
    assert batch_manifest_schema["properties"]["schema"]["const"] == (release_evidence.PRODUCTION_BATCH_MANIFEST_SCHEMA)
    assert set(batch_manifest_schema["required"]) == release_evidence.PRODUCTION_BATCH_MANIFEST_FIELDS
    assert set(batch_manifest_schema["properties"]["categories"]["items"]["required"]) == (
        release_evidence.PRODUCTION_BATCH_CATEGORY_FIELDS
    )
    assert handoff_schema["properties"]["schema"]["const"] == release_evidence.PRODUCTION_HANDOFF_SCHEMA
    assert handoff_schema["properties"]["schema_version"]["const"] == 2
    assert set(handoff_schema["required"]) == release_evidence.PRODUCTION_HANDOFF_FIELDS


def test_production_topology_json_schema_matches_runtime_contract(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "deploy" / "release" / "production-topology-report.schema.json").read_text(encoding="utf-8")
    )
    live_schema = json.loads(
        (root / "deploy" / "release" / "production-topology-live-probe.schema.json").read_text(encoding="utf-8")
    )
    statement_path, statement, _, policy = _production_gate_statement(tmp_path, "production_topology")
    report = json.loads((tmp_path / release_evidence.PRODUCTION_TOPOLOGY_REPORT).read_text(encoding="utf-8"))
    live_report = json.loads((tmp_path / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT).read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    Draft202012Validator.check_schema(live_schema)
    Draft202012Validator(live_schema).validate(live_report)
    _validate_specialized_evidence(statement_path, "production_topology", statement, policy=policy)


def _replace_production_topology_live_probe(
    tmp_path: Path,
    statement: dict[str, object],
    production_report: dict[str, object],
    probe: dict[str, object],
) -> None:
    probe_path = tmp_path / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
    probe_path.write_text(json.dumps(probe), encoding="utf-8")
    artifacts = production_report["artifacts"]
    assert isinstance(artifacts, list)
    artifact = next(
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("path") == release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
    )
    artifact["size"] = probe_path.stat().st_size
    artifact["sha256"] = hashlib.sha256(probe_path.read_bytes()).hexdigest()
    (tmp_path / "production-evidence-report.json").write_text(json.dumps(production_report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("topology_digest", "not bound to the approved deployment"),
        ("single_zone", "Kubernetes observation is incomplete"),
        ("workload_not_ready", "workload is not ready and governed"),
        ("mutable_image", "workload is not ready and governed"),
        ("ocr_wrong_image", "workload is not ready and governed"),
        ("missing_hpa", "workload is not ready and governed"),
        ("gateway_host", "Gateway observation is invalid"),
        ("mcp_not_rejected", "mcp endpoint observation is invalid"),
        ("credentials", "not bound to the approved deployment"),
    ],
)
def test_production_topology_live_probe_rejects_unobserved_or_unsafe_runtime(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    statement_path, statement, production_report, policy = _production_gate_statement(tmp_path, "production_topology")
    probe = json.loads((tmp_path / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT).read_text(encoding="utf-8"))
    if mutation == "topology_digest":
        probe["topology_report_sha256"] = "0" * 64
    elif mutation == "single_zone":
        probe["kubernetes"]["availability_zones"] = ["us-east-1a"]
    elif mutation == "workload_not_ready":
        probe["workloads"][0]["ready_replicas"] = 2
    elif mutation == "mutable_image":
        probe["workloads"][0]["image_digests"] = ["registry.example/pharma:latest"]
    elif mutation == "ocr_wrong_image":
        workload = next(item for item in probe["workloads"] if item["name"] == "pharma-ocr")
        subject = statement["subject"]
        assert isinstance(subject, dict)
        targets = subject["targets"]
        assert isinstance(targets, dict)
        workload["image_digests"] = [targets["api"]]
    elif mutation == "missing_hpa":
        workload = next(item for item in probe["workloads"] if item["name"] == "pharma-api")
        workload["hpa_present"] = False
    elif mutation == "gateway_host":
        probe["gateway"]["route_hosts"] = ["mcp.pharma-assurance.net", "wrong.pharma-assurance.net"]
    elif mutation == "mcp_not_rejected":
        probe["endpoints"]["mcp"]["status_code"] = 200
        probe["endpoints"]["mcp"]["unauthenticated_rejected"] = False
    else:
        probe["credentials_recorded"] = True
    _replace_production_topology_live_probe(tmp_path, statement, production_report, probe)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "production_topology", statement, policy=policy)


def _replace_production_topology_detail(
    tmp_path: Path,
    statement: dict[str, object],
    production_report: dict[str, object],
    detail: dict[str, object],
) -> None:
    detail_path = tmp_path / release_evidence.PRODUCTION_TOPOLOGY_REPORT
    detail_path.write_text(json.dumps(detail), encoding="utf-8")
    artifacts = production_report["artifacts"]
    assert isinstance(artifacts, list)
    artifact = next(
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("path") == release_evidence.PRODUCTION_TOPOLOGY_REPORT
    )
    artifact["size"] = detail_path.stat().st_size
    artifact["sha256"] = hashlib.sha256(detail_path.read_bytes()).hexdigest()
    probe_path = tmp_path / release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["topology_report_sha256"] = hashlib.sha256(detail_path.read_bytes()).hexdigest()
    probe_path.write_text(json.dumps(probe), encoding="utf-8")
    probe_artifact = next(
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("path") == release_evidence.PRODUCTION_TOPOLOGY_LIVE_REPORT
    )
    probe_artifact["size"] = probe_path.stat().st_size
    probe_artifact["sha256"] = hashlib.sha256(probe_path.read_bytes()).hexdigest()
    (tmp_path / "production-evidence-report.json").write_text(json.dumps(production_report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)


def test_scale_production_topology_accepts_the_versioned_event_profile(tmp_path: Path) -> None:
    statement_path, statement, production_report, policy = _production_gate_statement(tmp_path, "production_topology")
    subject = statement["subject"]
    assert isinstance(subject, dict)
    tested_at = datetime.fromisoformat(str(production_report["tested_at"]))
    detail = _valid_production_topology_report(subject, tested_at, profile="scale_production")
    _replace_production_topology_detail(tmp_path, statement, production_report, detail)

    _validate_specialized_evidence(statement_path, "production_topology", statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("local_environment", "local or development"),
        ("postgres16", "component does not meet"),
        ("postgres17_without_adr", "unapproved legacy"),
        ("ragflow_critical_path", "unapproved legacy"),
        ("shared_entrypoint", "exactly two distinct"),
        ("valkey8", "component does not meet"),
        ("opensearch_under_replicated", "component does not meet"),
        ("core_with_kafka", "transactional outbox"),
        ("scale_without_kafka", "event data baseline"),
        ("authority_drift", "authority boundaries"),
        ("resilience_gap", "resilience controls"),
        ("ragflow_reference_drift", "references are incomplete"),
    ],
)
def test_production_topology_rejects_downgrades_and_critical_path_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    statement_path, statement, production_report, policy = _production_gate_statement(tmp_path, "production_topology")
    detail = json.loads((tmp_path / release_evidence.PRODUCTION_TOPOLOGY_REPORT).read_text(encoding="utf-8"))
    components = detail["components"]
    migration = detail["migration"]
    entrypoints = detail["entrypoints"]
    event_projection = detail["event_projection"]
    authority = detail["authority"]
    resilience = detail["resilience"]
    references = detail["references"]
    assert all(
        isinstance(value, dict)
        for value in (components, migration, entrypoints, event_projection, authority, resilience, references)
    )
    if mutation == "local_environment":
        detail["environment_id"] = "local-development"
    elif mutation == "postgres16":
        components["postgresql"]["version"] = "16.9"
    elif mutation == "postgres17_without_adr":
        components["postgresql"]["version"] = "17.8"
    elif mutation == "ragflow_critical_path":
        migration["ragflow_critical_path"] = True
    elif mutation == "shared_entrypoint":
        entrypoints["mcp_url"] = entrypoints["web_url"]
    elif mutation == "valkey8":
        components["valkey"]["version"] = "8.1.0"
    elif mutation == "opensearch_under_replicated":
        components["opensearch"]["replicas"] = 2
    elif mutation == "core_with_kafka":
        event_projection.update(
            {
                "mode": "kafka_cdc",
                "kafka_version": "4.1.0",
                "debezium_version": "3.4.0",
                "clickhouse_enabled": True,
                "iceberg_enabled": True,
            }
        )
    elif mutation == "scale_without_kafka":
        detail["profile"] = "scale_production"
    elif mutation == "authority_drift":
        authority["search_role"] = "canonical"
    elif mutation == "resilience_gap":
        resilience["postgres_pitr"] = False
    else:
        references["ragflow_exit_plan"] = "DIFFERENT-EXIT-PLAN"
    _replace_production_topology_detail(tmp_path, statement, production_report, detail)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, "production_topology", statement, policy=policy)


def _production_batch_repository(tmp_path: Path) -> tuple[Path, Path, release_evidence.EvidencePolicy]:
    repo = _repository(tmp_path)
    release_root = repo / "deploy" / "release"
    release_root.mkdir(parents=True)
    source_root = Path(__file__).parents[1] / "deploy" / "release"
    for name in (
        "mcp-sender-constraint-report.schema.json",
        "production-evidence-batch-intake.schema.json",
        "production-evidence-batch-manifest.schema.json",
        "production-evidence-handoff-manifest.schema.json",
        "production-evidence-intake.schema.json",
        "production-evidence-report.schema.json",
        "production-topology-live-probe.schema.json",
        "production-topology-report.schema.json",
    ):
        shutil.copyfile(source_root / name, release_root / name)
    policy_path = release_root / "evidence-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "security_max_age_hours": {"production": 24},
                "categories": {
                    "operations_approval": {"max_age_hours": 720},
                    "performance": {"max_age_hours": 168},
                },
                "production_evidence_contracts": {
                    "operations_approval": {
                        "report_name": "production-evidence-report.json",
                        "checks": ["on_call"],
                        "approval_roles": ["operations"],
                        "minimum_artifacts": 1,
                        "require_independent_executor": False,
                    },
                    "performance": {
                        "report_name": "production-evidence-report.json",
                        "checks": ["sustained_load"],
                        "approval_roles": ["platform"],
                        "minimum_artifacts": 1,
                        "require_independent_executor": False,
                    },
                },
                "levels": {
                    "production": {
                        "require_release_security": True,
                        "require_signed_git_tag": True,
                        "require_bundle_signature": True,
                        "required_categories": ["operations_approval", "performance"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "deploy/release")
    _git(repo, "commit", "-m", "add production evidence contracts")
    return repo, policy_path, load_policy(policy_path)


def _production_batch_request(
    root: Path,
    policy: release_evidence.EvidencePolicy,
    category: str,
) -> Path:
    contract = policy.production_contracts[category]
    category_root = root / category
    category_root.mkdir(parents=True)
    artifact = category_root / "objective-report.json"
    artifact.write_text(json.dumps({"category": category, "status": "passed"}), encoding="utf-8")
    approvals: list[dict[str, object]] = []
    now = datetime.now(UTC).isoformat()
    for role in sorted(contract.approval_roles):
        approval = category_root / f"{role}-approval.json"
        approval.write_text(json.dumps({"role": role, "decision": "approved"}), encoding="utf-8")
        approvals.append(
            {
                "role": role,
                "source_path": str(approval),
                "destination": f"approvals/{role}-approval.json",
                "reference": f"APPROVAL-{category.upper()}-{role.upper()}",
                "organization": "External-Delivery-Organization",
                "approved_at": now,
            }
        )
    request = category_root / "intake.json"
    request.write_text(
        json.dumps(
            {
                "schema": release_evidence.PRODUCTION_INTAKE_SCHEMA,
                "schema_version": 1,
                "category": category,
                "environment_kind": "preproduction",
                "environment_id": "preprod-cn-east-1",
                "tested_at": now,
                "checks": sorted(contract.checks),
                "executor": {
                    "organization": "External-Assurance-Provider",
                    "team": "Validated-Delivery-Team",
                    "independent": contract.require_independent_executor,
                },
                "artifacts": [
                    {
                        "name": f"approved-{category}-report",
                        "source_path": str(artifact),
                        "destination": f"artifacts/{category}-report.json",
                        "reference": f"EVIDENCE-{category.upper()}-1",
                    }
                ],
                "approvals": approvals,
            }
        ),
        encoding="utf-8",
    )
    return request


def _production_batch_manifest(root: Path, policy: release_evidence.EvidencePolicy) -> Path:
    requests = [
        {"category": category, "request_path": str(_production_batch_request(root, policy, category))}
        for category in sorted(policy.production_contracts)
    ]
    manifest = root / "batch-intake.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": release_evidence.PRODUCTION_BATCH_INTAKE_SCHEMA,
                "schema_version": 1,
                "requests": requests,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_production_handoff_and_complete_batch_registration_are_atomic(tmp_path: Path) -> None:
    repo, policy_path, policy = _production_batch_repository(tmp_path)
    handoff = tmp_path / "production-handoff"

    handoff_result = prepare_production_evidence_handoff(
        repo=repo,
        policy_path=policy_path,
        output=handoff,
    )

    assert handoff_result["category_count"] == 2
    handoff_manifest = json.loads((handoff / "handoff-manifest.json").read_text(encoding="utf-8"))
    assert handoff_manifest["status"] == "requirements_only"
    assert handoff_manifest["production_claim"] is False
    assert {item["category"] for item in handoff_manifest["categories"]} == set(policy.production_contracts)
    assert "source_path" not in json.dumps(handoff_manifest)
    assert stat.S_IMODE(handoff.stat().st_mode) == 0o700
    verification = verify_production_evidence_handoff(
        repo=repo,
        policy_path=policy_path,
        handoff=handoff,
    )
    assert verification["status"] == "passed"
    assert verification["category_count"] == 2
    assert verification["signature_verified"] is False

    requirement = handoff / "requirements" / "performance.json"
    requirement.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="authoritative policy"):
        verify_production_evidence_handoff(
            repo=repo,
            policy_path=policy_path,
            handoff=handoff,
        )

    security = _security(tmp_path, repo, release_mode=True)
    intake_root = tmp_path / "external-intake"
    intake_root.mkdir()
    batch_intake = _production_batch_manifest(intake_root, policy)
    output = tmp_path / "registered-production"

    result = register_production_evidence_batch(
        repo=repo,
        policy_path=policy_path,
        security_directory=security,
        manifest_path=batch_intake,
        output=output,
    )

    assert result["category_count"] == 2
    assert result["production_claim"] is False
    statements = collect_release_statements([], [output])
    assert [path.parent.name for path in statements] == ["operations_approval", "performance"]
    batch_manifest = json.loads((output / "batch-manifest.json").read_text(encoding="utf-8"))
    assert batch_manifest["schema"] == release_evidence.PRODUCTION_BATCH_MANIFEST_SCHEMA
    assert batch_manifest["production_claim"] is False
    audit = audit_release(
        repo=repo,
        policy_path=policy_path,
        level_name="production",
        security_directory=security,
        statements=statements,
        release_tag=None,
    )
    assert audit["missing_categories"] == []
    assert audit["status"] == "blocked"
    assert all("missing evidence category" not in blocker for blocker in audit["blockers"])

    batch_manifest["categories"][0]["statement_sha256"] = "0" * 64
    (output / "batch-manifest.json").write_text(json.dumps(batch_manifest), encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="statement binding is invalid"):
        collect_release_statements([], [output])


def test_signed_production_handoff_verifies_offline_and_rejects_tampering(tmp_path: Path) -> None:
    repo, policy_path, policy = _production_batch_repository(tmp_path)
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "handoff-signing.pem"
    public_path = tmp_path / "handoff-signing.pub"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    handoff = tmp_path / "signed-production-handoff"

    result = prepare_production_evidence_handoff(
        repo=repo,
        policy_path=policy_path,
        output=handoff,
        signing_key_path=private_path,
        signing_key_id="production-handoff-test-v1",
    )

    assert result["signature_present"] is True
    assert (
        verify_production_evidence_handoff(
            repo=repo,
            policy_path=policy_path,
            handoff=handoff,
            trusted_public_key=public_path,
        )["signature_verified"]
        is True
    )
    offline = verify_production_evidence_handoff_offline(
        handoff=handoff,
        trusted_public_key=public_path,
    )
    assert offline["status"] == "passed"
    assert offline["category_count"] == len(policy.production_contracts)
    assert offline["signature_verified"] is True

    wrong_private_key = Ed25519PrivateKey.generate()
    wrong_public_path = tmp_path / "wrong-handoff-signing.pub"
    wrong_public_path.write_bytes(
        wrong_private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    with pytest.raises(ReleaseEvidenceError, match="signature metadata"):
        verify_production_evidence_handoff_offline(
            handoff=handoff,
            trusted_public_key=wrong_public_path,
        )

    requirement = handoff / "requirements" / "performance.json"
    requirement.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="bundled policy"):
        verify_production_evidence_handoff_offline(
            handoff=handoff,
            trusted_public_key=public_path,
        )


def test_signed_production_handoff_binds_goal_matrix_for_offline_review(tmp_path: Path) -> None:
    repo, policy_path, _ = _production_batch_repository(tmp_path)
    policy_document = json.loads(policy_path.read_text(encoding="utf-8"))
    categories = sorted(policy_document["levels"]["production"]["required_categories"])
    policy_document["security_max_age_hours"]["pilot"] = 24
    policy_document["levels"]["pilot"] = {
        "require_release_security": False,
        "require_signed_git_tag": False,
        "require_bundle_signature": False,
        "required_categories": categories,
    }
    policy_path.write_text(json.dumps(policy_document), encoding="utf-8")
    _compact_goal_matrix(policy_path.parent, categories)
    _git(repo, "add", "deploy/release")
    _git(repo, "commit", "-m", "bind goal completion contract")

    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "handoff-goal-private.pem"
    public_path = tmp_path / "handoff-goal-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    handoff = tmp_path / "goal-handoff"

    prepare_production_evidence_handoff(
        repo=repo,
        policy_path=policy_path,
        output=handoff,
        signing_key_path=private_path,
        signing_key_id="goal-handoff-v1",
    )

    assert (handoff / "policy" / "goal-section-19-matrix.json").is_file()
    assert (handoff / "policy" / "goal-section-19-matrix.schema.json").is_file()
    assert (handoff / "schemas" / "production-topology-live-probe.schema.json").is_file()
    assert (handoff / "schemas" / "production-topology-report.schema.json").is_file()
    assert (
        verify_production_evidence_handoff(
            repo=repo,
            policy_path=policy_path,
            handoff=handoff,
            trusted_public_key=public_path,
        )["signature_verified"]
        is True
    )
    assert (
        verify_production_evidence_handoff_offline(
            handoff=handoff,
            trusted_public_key=public_path,
        )["signature_verified"]
        is True
    )

    matrix_path = handoff / "policy" / "goal-section-19-matrix.json"
    matrix_path.write_text(matrix_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="inventory"):
        verify_production_evidence_handoff_offline(
            handoff=handoff,
            trusted_public_key=public_path,
        )


def test_unsigned_handoff_rejects_rewritten_schema_snapshot(tmp_path: Path) -> None:
    repo, policy_path, _ = _production_batch_repository(tmp_path)
    handoff = tmp_path / "unsigned-production-handoff"
    prepare_production_evidence_handoff(repo=repo, policy_path=policy_path, output=handoff)
    schema_path = handoff / "schemas" / "production-evidence-intake.schema.json"
    schema_path.write_text("{}\n", encoding="utf-8")
    manifest_path = handoff / "handoff-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if item["path"] == "schemas/production-evidence-intake.schema.json":
            item["size"] = schema_path.stat().st_size
            item["sha256"] = hashlib.sha256(schema_path.read_bytes()).hexdigest()
            break
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="authoritative repository"):
        verify_production_evidence_handoff(
            repo=repo,
            policy_path=policy_path,
            handoff=handoff,
        )


def test_production_batch_rolls_back_after_a_late_invalid_request(tmp_path: Path) -> None:
    repo, policy_path, policy = _production_batch_repository(tmp_path)
    security = _security(tmp_path, repo, release_mode=True)
    intake_root = tmp_path / "external-intake"
    intake_root.mkdir()
    batch_intake = _production_batch_manifest(intake_root, policy)
    performance_request = intake_root / "performance" / "intake.json"
    document = json.loads(performance_request.read_text(encoding="utf-8"))
    document["checks"] = []
    performance_request.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "registered-production"

    with pytest.raises(ReleaseEvidenceError, match="every contracted check"):
        register_production_evidence_batch(
            repo=repo,
            policy_path=policy_path,
            security_directory=security,
            manifest_path=batch_intake,
            output=output,
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".registered-production.batch-*"))


def test_production_batch_rejects_partial_or_non_release_inputs(tmp_path: Path) -> None:
    repo, policy_path, policy = _production_batch_repository(tmp_path)
    intake_root = tmp_path / "external-intake"
    intake_root.mkdir()
    batch_intake = _production_batch_manifest(intake_root, policy)
    document = json.loads(batch_intake.read_text(encoding="utf-8"))
    document["requests"].pop()
    batch_intake.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="batch is incomplete"):
        register_production_evidence_batch(
            repo=repo,
            policy_path=policy_path,
            security_directory=_security(tmp_path, repo, release_mode=True),
            manifest_path=batch_intake,
            output=tmp_path / "partial-output",
        )

    batch_intake = _production_batch_manifest(tmp_path / "second-intake", policy)
    non_release_root = tmp_path / "non-release"
    non_release_root.mkdir()
    with pytest.raises(ReleaseEvidenceError, match="release-mode security"):
        register_production_evidence_batch(
            repo=repo,
            policy_path=policy_path,
            security_directory=_security(non_release_root, repo),
            manifest_path=batch_intake,
            output=tmp_path / "non-release-output",
        )


def test_statement_directory_discovery_is_bounded_and_rejects_aliases(tmp_path: Path) -> None:
    root = tmp_path / "statements"
    first = root / "browser" / "gate-statement.json"
    second = root / "quality" / "gate-statement.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("{}\n", encoding="utf-8")
    second.write_text("{}\n", encoding="utf-8")
    (root / "summary.json").write_text("{}\n", encoding="utf-8")

    assert collect_release_statements([], [root]) == [first.resolve(), second.resolve()]
    with pytest.raises(ReleaseEvidenceError, match="duplicate release gate statement path"):
        collect_release_statements([first], [root])

    alias = root / "runtime"
    alias.symlink_to(first.parent, target_is_directory=True)
    with pytest.raises(ReleaseEvidenceError, match="cannot be a symbolic link"):
        collect_release_statements([], [root])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("local_environment", "local or development"),
        ("wrong_subject", "release subject"),
        ("failed_check", "every contracted check"),
        ("no_artifacts", "insufficient bounded artifacts"),
        ("missing_approval", "required approval roles"),
        ("approval_before_test", "predates the tested evidence"),
    ],
)
def test_external_production_evidence_rejects_unverifiable_reports(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    category = "performance"
    statement_path, statement, report, policy = _production_gate_statement(tmp_path, category)
    if mutation == "local_environment":
        report["environment_id"] = "local-development"
    elif mutation == "wrong_subject":
        report["subject"] = {"git_commit": "f" * 40}
    elif mutation == "failed_check":
        checks = report["checks"]
        assert isinstance(checks, dict)
        checks["fault_injection"] = False
    elif mutation == "no_artifacts":
        report["artifacts"] = []
    elif mutation == "approval_before_test":
        approvals = report["approvals"]
        assert isinstance(approvals, list) and isinstance(approvals[0], dict)
        tested_at = datetime.fromisoformat(str(report["tested_at"]))
        approvals[0]["approved_at"] = (tested_at - timedelta(hours=1)).isoformat()
    else:
        report["approvals"] = []
    contract = policy.production_contracts[category]
    (tmp_path / contract.report_name).write_text(json.dumps(report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)


def test_penetration_evidence_requires_an_independent_executor(tmp_path: Path) -> None:
    category = "penetration_test"
    statement_path, statement, report, policy = _production_gate_statement(tmp_path, category)
    executor = report["executor"]
    assert isinstance(executor, dict)
    executor["independent"] = False
    contract = policy.production_contracts[category]
    (tmp_path / contract.report_name).write_text(json.dumps(report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)

    with pytest.raises(ReleaseEvidenceError, match="non-independent executor"):
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)


def test_external_production_evidence_allows_bounded_approval_clock_skew(tmp_path: Path) -> None:
    category = "performance"
    statement_path, statement, report, policy = _production_gate_statement(tmp_path, category)
    approvals = report["approvals"]
    assert isinstance(approvals, list) and isinstance(approvals[0], dict)
    tested_at = datetime.fromisoformat(str(report["tested_at"]))
    approvals[0]["approved_at"] = (tested_at - timedelta(minutes=4)).isoformat()
    contract = policy.production_contracts[category]
    (tmp_path / contract.report_name).write_text(json.dumps(report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)

    _validate_specialized_evidence(statement_path, category, statement, policy=policy)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("forged_artifact_digest", "unbound or duplicate artifact"),
        ("missing_artifact_file", "unbound or duplicate artifact"),
        ("reused_approval_artifact", "unbound or duplicate approval"),
        ("unreferenced_attachment", "unreferenced attachments"),
        ("unknown_report_field", "not approved production-environment evidence"),
        ("unknown_artifact_field", "invalid artifact"),
    ],
)
def test_production_evidence_requires_every_artifact_and_approval_to_be_bound(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    category = "billing_provider"
    statement_path, statement, report, policy = _production_gate_statement(tmp_path, category)
    artifacts = report["artifacts"]
    approvals = report["approvals"]
    assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
    assert isinstance(approvals, list) and isinstance(approvals[0], dict)
    if mutation == "forged_artifact_digest":
        artifacts[0]["sha256"] = "0" * 64
    elif mutation == "missing_artifact_file":
        (tmp_path / str(artifacts[0]["path"])).unlink()
    elif mutation == "reused_approval_artifact":
        approvals[0]["artifact_path"] = artifacts[0]["path"]
        approvals[0]["artifact_size"] = artifacts[0]["size"]
        approvals[0]["artifact_sha256"] = artifacts[0]["sha256"]
    elif mutation == "unknown_report_field":
        report["notes"] = "ambiguous extension must be versioned"
    elif mutation == "unknown_artifact_field":
        artifacts[0]["status"] = "passed"
    else:
        extra = tmp_path / "artifacts" / "unreferenced.json"
        extra.write_text('{"status":"passed"}\n', encoding="utf-8")
    contract = policy.production_contracts[category]
    (tmp_path / contract.report_name).write_text(json.dumps(report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)


def test_capture_rejects_a_successful_command_without_required_production_report(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    root = Path(__file__).parents[1]
    policy = root / "deploy" / "release" / "evidence-policy.json"
    security = _security(tmp_path, repo)

    with pytest.raises(ReleaseEvidenceError, match="production-evidence-report.json"):
        capture_gate(
            repo=repo,
            policy_path=policy,
            category="performance",
            security_directory=security,
            output=tmp_path / "performance" / "gate-statement.json",
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            attachments=[],
        )


def test_failed_production_capture_preserves_root_cause_without_a_semantic_report(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    root = Path(__file__).parents[1]
    policy_path = root / "deploy" / "release" / "evidence-policy.json"
    policy = load_policy(policy_path)
    security = _security(tmp_path, repo)
    output = tmp_path / "performance-failed" / "gate-statement.json"
    expected_report = output.parent / policy.production_contracts["performance"].report_name

    statement, exit_code = capture_gate(
        repo=repo,
        policy_path=policy_path,
        category="performance",
        security_directory=security,
        output=output,
        command=[sys.executable, "-c", "raise SystemExit(17)"],
        attachments=[expected_report],
    )

    assert exit_code == 17
    assert statement["status"] == "failed"
    assert statement["missing_attachments"] == ["production-evidence-report.json"]
    assert output.is_file()


def _sender_constraint_statement(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], dict[str, object], release_evidence.EvidencePolicy]:
    statement_path, statement, production_report, policy = _production_gate_statement(tmp_path, "mcp_sender_constraint")
    tested_at = datetime.now(UTC)
    subject = statement["subject"]
    report: dict[str, object] = {
        "schema": "pharma.mcp-sender-constraint-evidence.v2",
        "schema_version": 2,
        "status": "passed",
        "environment_kind": "preproduction",
        "environment_id": "preprod-us-east-1",
        "tested_at": tested_at.isoformat(),
        "subject": subject,
        "idp_issuer_url": "https://identity.preprod.vendor.com",
        "resource_server_url": "https://mcp.preprod.customer.com/mcp",
        "clients": [
            {"name": "official-python-sdk", "version": "1.28.1", "dpop_supported": True},
            {"name": "enterprise-agent", "version": "4.2.0", "dpop_supported": True},
        ],
        "checks": {
            "access_token_signature": True,
            "ath_binding": True,
            "bearer_rejected": True,
            "htm_binding": True,
            "htu_binding": True,
            "iat_window": True,
            "jkt_binding": True,
            "jti_replay_rejected": True,
            "key_rotation": True,
            "replay_store_fail_closed": True,
            "token_revocation": True,
        },
        "replay_store": {"failure_mode": "fail_closed", "shared": True, "tls": True},
        "references": {
            "gateway_change": "CHG-GATEWAY-1024",
            "idp_change": "CHG-IDP-2048",
            "security_approval": "SEC-APPROVAL-4096",
        },
    }
    report_path = tmp_path / "mcp-sender-constraint-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    artifacts = production_report["artifacts"]
    assert isinstance(artifacts, list)
    artifacts.append(
        {
            "name": "mcp-sender-constraint-protocol-report",
            "path": report_path.name,
            "size": report_path.stat().st_size,
            "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "reference": "MCP-DPOP-PREPROD-REPORT",
        }
    )
    contract = policy.production_contracts["mcp_sender_constraint"]
    (tmp_path / contract.report_name).write_text(json.dumps(production_report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)
    return statement_path, statement, report, policy


def _rewrite_sender_constraint_detail(
    tmp_path: Path,
    statement: dict[str, object],
    report: dict[str, object],
    policy: release_evidence.EvidencePolicy,
) -> None:
    report_path = tmp_path / "mcp-sender-constraint-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    contract = policy.production_contracts["mcp_sender_constraint"]
    production_path = tmp_path / contract.report_name
    production_report = json.loads(production_path.read_text(encoding="utf-8"))
    artifacts = production_report["artifacts"]
    matching = [artifact for artifact in artifacts if artifact["path"] == report_path.name]
    assert len(matching) == 1
    matching[0]["size"] = report_path.stat().st_size
    matching[0]["sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    production_path.write_text(json.dumps(production_report), encoding="utf-8")
    _refresh_production_attachments(tmp_path, statement)


def test_mcp_sender_constraint_evidence_requires_real_preproduction_semantics(tmp_path: Path) -> None:
    statement_path, statement, _, policy = _sender_constraint_statement(tmp_path)

    _validate_specialized_evidence(statement_path, "mcp_sender_constraint", statement, policy=policy)


@pytest.mark.parametrize("invalid_environment", ["local", "development", "test"])
def test_mcp_sender_constraint_evidence_rejects_local_self_tests(
    tmp_path: Path,
    invalid_environment: str,
) -> None:
    statement_path, statement, report, policy = _sender_constraint_statement(tmp_path)
    report["environment_kind"] = invalid_environment
    _rewrite_sender_constraint_detail(tmp_path, statement, report, policy)

    with pytest.raises(ReleaseEvidenceError, match="approved environment evidence"):
        _validate_specialized_evidence(statement_path, "mcp_sender_constraint", statement, policy=policy)


def test_mcp_sender_constraint_evidence_rejects_partial_security_checks(tmp_path: Path) -> None:
    statement_path, statement, report, policy = _sender_constraint_statement(tmp_path)
    checks = report["checks"]
    assert isinstance(checks, dict)
    checks["token_revocation"] = False
    _rewrite_sender_constraint_detail(tmp_path, statement, report, policy)

    with pytest.raises(ReleaseEvidenceError, match="every required check"):
        _validate_specialized_evidence(statement_path, "mcp_sender_constraint", statement, policy=policy)


def test_mcp_sender_constraint_evidence_rejects_reserved_test_endpoint(tmp_path: Path) -> None:
    statement_path, statement, report, policy = _sender_constraint_statement(tmp_path)
    report["idp_issuer_url"] = "https://identity.preprod.example.test"
    _rewrite_sender_constraint_detail(tmp_path, statement, report, policy)

    with pytest.raises(ReleaseEvidenceError, match="invalid idp_issuer_url"):
        _validate_specialized_evidence(statement_path, "mcp_sender_constraint", statement, policy=policy)


def test_mcp_sender_constraint_evidence_rejects_cross_release_report(tmp_path: Path) -> None:
    statement_path, statement, report, policy = _sender_constraint_statement(tmp_path)
    subject = report["subject"]
    assert isinstance(subject, dict)
    report["subject"] = {**subject, "git_commit": "f" * 40}
    _rewrite_sender_constraint_detail(tmp_path, statement, report, policy)

    with pytest.raises(ReleaseEvidenceError, match="release subject"):
        _validate_specialized_evidence(statement_path, "mcp_sender_constraint", statement, policy=policy)


def test_mcp_sender_constraint_json_schema_matches_runtime_contract() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "deploy" / "release" / "mcp-sender-constraint-report.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["schema"]["const"] == release_evidence.MCP_SENDER_CONSTRAINT_SCHEMA
    assert schema["properties"]["schema_version"]["const"] == 2
    assert set(schema["required"]) == release_evidence.MCP_SENDER_CONSTRAINT_FIELDS
    assert set(schema["properties"]["checks"]["required"]) == release_evidence.MCP_SENDER_CONSTRAINT_CHECKS


def test_production_policy_requires_explicit_data_model_and_sender_checks() -> None:
    root = Path(__file__).parents[1]
    policy = load_policy(root / "deploy" / "release" / "evidence-policy.json")

    data_checks = policy.production_contracts["data_licensing"].checks
    assert "domain_coverage" not in data_checks
    assert {
        "literature_coverage",
        "patent_coverage",
        "target_coverage",
        "structure_coverage",
        "activity_coverage",
        "pipeline_coverage",
        "clinical_coverage",
        "company_coverage",
        "deal_coverage",
        "regulatory_coverage",
    } <= data_checks
    assert {
        "model_strict_schema",
        "model_usage_request_ids",
        "model_cost_accounting",
        "model_citation_grounding",
        "model_prompt_injection_defense",
        "model_rate_limit_backoff",
        "model_failure_recovery",
    } <= policy.production_contracts["external_services"].checks
    sender_contract = policy.production_contracts["mcp_sender_constraint"]
    assert sender_contract.minimum_artifacts >= 2
    assert sender_contract.approval_roles == frozenset({"security", "platform"})


def test_release_evidence_cli_runs_directly_from_the_repository() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(  # noqa: S603 - the interpreter and repository script are fixed test inputs.
        [sys.executable, "scripts/release_evidence.py", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Capture, assemble and verify release evidence" in completed.stdout
