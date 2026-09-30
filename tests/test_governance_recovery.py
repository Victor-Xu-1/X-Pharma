from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import recover_stale_extraction_runs
from pharma_intel.models import (
    ExtractionRun,
    RunState,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
)


def _version(
    session: Session,
    tenant_id: str,
    logical_path: str,
    *,
    stale: bool,
) -> tuple[SourceVersion, ExtractionRun]:
    now = datetime.now(UTC)
    asset = SourceAsset(
        tenant_id=tenant_id,
        data_source_id="source-1",
        logical_path=logical_path,
        source_uri=f"https://source.example/{logical_path}",
        file_name=logical_path.rsplit("/", 1)[-1],
        extension=".md",
        processing_mode="parse",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(asset)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant_id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=10,
        source_modified_at=now,
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.RUNNING,
        state=SourceVersionState.GOVERNANCE_PENDING,
        raw_object_uri="file:///raw/source",
        extracted_text_object_uri="file:///text/source",
    )
    session.add(version)
    session.flush()
    run = ExtractionRun(
        tenant_id=tenant_id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.13.0",
        model_provider="openai-compatible",
        model_name="mimo-v2.5",
        prompt_sha256="b" * 64,
        policy_sha256="c" * 64,
        input_sha256="d" * 64,
        status=RunState.RUNNING,
        started_at=now - timedelta(hours=3) if stale else now,
    )
    session.add(run)
    session.flush()
    return version, run


def test_recover_stale_runs_resets_retryable_versions_and_leaves_fresh_runs(
    session: Session,
    tenant: Tenant,
) -> None:
    stale_version, stale_run = _version(session, tenant.id, "stale.md", stale=True)
    fresh_version, fresh_run = _version(session, tenant.id, "fresh.md", stale=False)
    session.commit()

    recovered = recover_stale_extraction_runs(
        session,
        Settings(ai_stale_run_seconds=300),
        tenant.id,
        now=datetime.now(UTC),
    )

    assert recovered == 1
    assert stale_run.status == RunState.FAILED
    assert stale_run.completed_at is not None
    assert stale_run.validation_errors[-1]["code"] == "stale_run_recovered"
    assert stale_version.state == SourceVersionState.PARSED
    assert stale_version.governance_status == StageStatus.NOT_STARTED
    assert fresh_run.status == RunState.RUNNING
    assert fresh_version.state == SourceVersionState.GOVERNANCE_PENDING
