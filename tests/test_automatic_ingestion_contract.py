from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_automatic_ingestion_acceptance_observes_scheduler_without_manual_source_mutation() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-automatic-ingestion.sh"
    text = script.read_text(encoding="utf-8")
    bash = shutil.which("bash")
    assert bash is not None

    completed = subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "TEMPORAL_SCHEDULER_ENABLED" in text
    assert "source-ingest-$source_id-%" in text
    assert "pharma.automatic-ingestion-evidence.v4" in text
    assert "response_models" in text
    assert ":'ai_model'" not in text
    assert "AI_GOVERNANCE_ENABLED" in text
    assert "accounted_segments" in text
    assert "quote_verified_facts" in text
    assert "baseline_versions" in text
    assert "new_versions" in text
    assert "baseline_run_created_at" in text
    assert "observed_run_created_at" in text
    assert "ai_policy_sha256" in text
    assert "baseline_policy_runs" in text
    assert "observed_policy_runs" in text
    assert "inflight_current_versions" in text
    assert "source has in-flight downstream processing at the acceptance watermark" in text
    assert "AND (created_at, id::uuid) >" in text
    assert "id::text <> coalesce" not in text
    assert 'scheduler_outcome = "new_version"' in text
    assert 'scheduler_outcome = "policy_reprocess"' in text
    assert 'scheduler_outcome = "unchanged"' in text
    assert "pipeline_complete=false" in text
    assert "governance_status = 'SUCCEEDED'" in text
    assert "retrieval_status = 'SUCCEEDED'" in text
    assert "downstream processing failed" in text
    assert "processing_failure_grace_seconds=60" in text
    assert "processing_failure_observed_epoch" in text
    assert "continue" in text
    assert '"manual_trigger_used": False' in text
    assert '"source_schedule_mutated": False' in text
    assert '"source_content_created_by_test": False' in text
    assert "pharma-ingest once" not in text
    assert "UPDATE data_sources" not in text
    assert text.index("source_record=$(\n") < text.index("preflight_json=")
    assert "LEFT JOIN LATERAL" in text
    assert "CLINICALTRIALS_GOV" in text
    assert "PUBMED" in text
    assert 'project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"' in text
    assert "--project-name NAME" in text
    assert 'compose=(docker compose --project-name "$project_name")' in text
    assert 'export COMPOSE_FILE="compose.yaml:compose.dev.yaml:compose.telemetry.yaml"' in text
    assert "project=$project_name" in text
    assert "resolved.source_version_id = er.source_version_id" in text
    assert "failed runs for audit" in text


def test_pilot_ingestion_observes_scheduler_before_idempotence_scans() -> None:
    root = Path(__file__).parents[1]
    text = (root / "scripts" / "verify-pilot-ingestion.sh").read_text(encoding="utf-8")

    assert text.index("verify-automatic-ingestion.sh") < text.index("verify-local-ingestion.sh")
    local_ingestion = (root / "scripts" / "verify-local-ingestion.sh").read_text(encoding="utf-8")
    assert "response_models" in local_ingestion
    assert ":'ai_model'" not in local_ingestion
    assert "CLINICALTRIALS_GOV" in local_ingestion
    assert "PUBMED" in local_ingestion
    assert 'project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"' in text
    assert 'project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"' in local_ingestion
    assert '"$root/scripts/verify-automatic-ingestion.sh"' in text
    assert '--project-name "$project_name"' in text
    assert 'compose=(docker compose --project-name "$project_name")' in local_ingestion
    assert 'export COMPOSE_FILE="compose.yaml:compose.dev.yaml:compose.telemetry.yaml"' in local_ingestion


def test_automatic_ingestion_acceptance_is_packaged_and_exposed_by_make() -> None:
    root = Path(__file__).parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")

    assert "automatic-ingestion-acceptance:" in makefile
    assert "verify-automatic-ingestion.sh" in makefile
    assert "verify-automatic-ingestion.sh" in dockerfile
    assert "verify-pilot-ingestion.sh" in dockerfile


def test_ingestion_readiness_gate_never_mutates_or_manually_scans_a_source() -> None:
    root = Path(__file__).parents[1]
    script = (root / "scripts" / "capture_ingestion_readiness.py").read_text(encoding="utf-8")
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert 'pharma-ingest", "readiness' in script
    assert 'pharma-ingest", "once' not in script
    assert "scan_registered_sources" not in script
    assert "UPDATE data_sources" not in script
    assert "real_source_automatic_ingestion_verified" in script
    assert "ingestion-readiness-acceptance:" in makefile
    assert "capture_ingestion_readiness.py" in (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")
