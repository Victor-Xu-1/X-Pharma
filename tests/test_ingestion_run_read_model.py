from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pharma_intel.ingest.run_read_model import IngestionRunReadService
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    IngestionRun,
    RunState,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
)


def test_run_read_model_aggregates_real_source_version_stage_progress(session: Session, tenant: Tenant) -> None:
    source = DataSource(
        tenant_id=tenant.id,
        name="Stage graph source",
        source_type=DataSourceType.FOLDER,
        root_uri="/sources/stage-graph",
        owner="Data Operations",
        authorization_scopes=["contract:stage-graph"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    first_asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="first.pdf",
        source_uri="file:///sources/stage-graph/first.pdf",
        file_name="first.pdf",
        extension=".pdf",
        processing_mode="parse",
    )
    second_asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="second.pdf",
        source_uri="file:///sources/stage-graph/second.pdf",
        file_name="second.pdf",
        extension=".pdf",
        processing_mode="parse",
    )
    session.add_all([first_asset, second_asset])
    session.flush()
    first = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=first_asset.id,
        version_number=1,
        content_sha256="1" * 64,
        size_bytes=100,
        state=SourceVersionState.GOVERNANCE_PENDING,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.RUNNING,
    )
    second = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=second_asset.id,
        version_number=1,
        content_sha256="2" * 64,
        size_bytes=200,
        state=SourceVersionState.FAILED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.FAILED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.NOT_STARTED,
    )
    session.add_all([first, second])
    session.flush()
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="stage-graph-correlation",
        temporal_workflow_id="source-ingest-stage-graph",
        temporal_run_id="temporal-stage-graph-run",
        state=RunState.PARTIAL,
        result={"version_ids": [first.id, second.id]},
        counters={"discovered": 2},
    )
    session.add(run)
    session.commit()

    result = IngestionRunReadService(session, tenant.id).build(run)

    assert result.effective_state == RunState.RUNNING
    assert result.cancelable is True
    assert result.total_versions == 2
    assert result.completed_versions == 1
    assert 0 < result.progress_percent < 100
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["snapshot"].status == "succeeded"
    assert stages["parse"].status == "failed"
    assert stages["parse"].completed_items == 1
    assert stages["parse"].failed_items == 1
    assert stages["governance"].status == "running"


def test_terminal_failed_version_does_not_leave_run_effectively_running(
    session: Session,
    tenant: Tenant,
) -> None:
    source = DataSource(
        tenant_id=tenant.id,
        name="Terminal failed source",
        source_type=DataSourceType.FOLDER,
        root_uri="/sources/terminal-failed",
        owner="Data Operations",
        authorization_scopes=["contract:terminal-failed"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="blocked.pdf",
        source_uri="file:///sources/terminal-failed/blocked.pdf",
        file_name="blocked.pdf",
        extension=".pdf",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="3" * 64,
        size_bytes=300,
        state=SourceVersionState.FAILED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.FAILED,
        parse_status=StageStatus.NOT_STARTED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.NOT_STARTED,
    )
    session.add(version)
    session.flush()
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="terminal-failed-correlation",
        temporal_workflow_id="source-ingest-terminal-failed",
        temporal_run_id="temporal-terminal-failed-run",
        state=RunState.PARTIAL,
        result={"version_ids": [version.id]},
        counters={"discovered": 1, "failed": 1},
    )
    session.add(run)
    session.commit()

    result = IngestionRunReadService(session, tenant.id).build(run)

    assert result.effective_state == RunState.PARTIAL
    assert result.cancelable is False
    assert result.progress_percent == 100
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["malware_scan"].status == "failed"
    assert stages["parse"].status == "not_started"
