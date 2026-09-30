from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pharma_intel.governance.lifecycle import DataLifecycleService, LifecycleConflict
from pharma_intel.models import (
    DataExportJob,
    DataSource,
    DataSourceType,
    ExtractionRun,
    GovernanceStatus,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal


def _principal(session: Session, tenant: Tenant) -> Principal:
    user = User(
        tenant_id=tenant.id,
        email="lifecycle@example.test",
        normalized_email=f"lifecycle-{tenant.id}@example.test",
        display_name="Lifecycle Operator",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    return Principal(tenant.id, user.id, "user", frozenset({"commercial:read", "commercial:write"}))


def _expired_job(session: Session, tenant: Tenant, store: FileSystemObjectStore) -> DataExportJob:
    artifact = b'{"id":"record-1"}\n'
    manifest = b'{"schema":"manifest"}'
    artifact_sha = hashlib.sha256(artifact).hexdigest()
    manifest_sha = hashlib.sha256(manifest).hexdigest()
    job_id = "11111111-1111-4111-8111-111111111111"
    stored_artifact = store.put_bytes(tenant.id, f"exports-{job_id}", artifact, artifact_sha, ".jsonl")
    stored_manifest = store.put_bytes(tenant.id, f"export-manifests-{job_id}", manifest, manifest_sha, ".json")
    completed = datetime.now(UTC) - timedelta(hours=2)
    job = DataExportJob(
        id=job_id,
        tenant_id=tenant.id,
        billing_account_id="22222222-2222-4222-8222-222222222222",
        subscription_id="33333333-3333-4333-8333-333333333333",
        agent_client_id="44444444-4444-4444-8444-444444444444",
        actor_type="agent",
        subject_id="agent-subject",
        idempotency_key="export-request-1",
        request_sha256="a" * 64,
        dataset="entities",
        license_policy_version="test-v1",
        license_policy_sha256="b" * 64,
        license_attribution="test",
        export_format="jsonl",
        filters_json={},
        fields_json=["id"],
        max_records=10,
        max_billable_units=Decimal("10"),
        state="completed",
        approval_required=False,
        workflow_id=f"data-export-{job_id}",
        record_count=1,
        artifact_uri=stored_artifact.uri,
        artifact_sha256=artifact_sha,
        artifact_bytes=len(artifact),
        manifest_uri=stored_manifest.uri,
        manifest_sha256=manifest_sha,
        manifest_signature="signature",
        manifest_key_id="key-1",
        requested_at=completed,
        completed_at=completed,
        expires_at=completed + timedelta(minutes=5),
    )
    session.add(job)
    session.commit()
    return job


def _missing_source_asset(
    session: Session,
    tenant: Tenant,
    store: FileSystemObjectStore,
    *,
    suffix: str = "1",
) -> tuple[SourceAsset, SourceVersion, str, str]:
    source = DataSource(
        tenant_id=tenant.id,
        name=f"Lifecycle source {suffix}",
        source_type=DataSourceType.FOLDER,
        root_uri=f"/source/{suffix}",
        owner="Research Operations",
        authorization_scopes=["contract:lifecycle-test"],
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    missing_at = datetime.now(UTC) - timedelta(hours=2)
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path=f"target-{suffix}.md",
        source_uri=f"file:///source/{suffix}/target.md",
        file_name=f"target-{suffix}.md",
        extension=".md",
        processing_mode="parse",
        state=SourceAssetState.MISSING,
        first_seen_at=missing_at - timedelta(days=1),
        last_seen_at=missing_at,
        missing_since=missing_at,
    )
    session.add(asset)
    session.flush()
    raw = f"EGFR source {suffix}".encode()
    text = f"EGFR extracted evidence {suffix}".encode()
    raw_digest = hashlib.sha256(raw).hexdigest()
    text_digest = hashlib.sha256(text).hexdigest()
    raw_object = store.put_bytes(tenant.id, "raw", raw, raw_digest, ".md")
    text_object = store.put_bytes(tenant.id, "extracted", text, text_digest, ".txt")
    document = SourceDocument(
        tenant_id=tenant.id,
        title=f"Target source {suffix}",
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256=raw_digest,
    )
    session.add(document)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=raw_digest,
        size_bytes=len(raw),
        raw_object_uri=raw_object.uri,
        extracted_text_object_uri=text_object.uri,
        extracted_text_sha256=text_digest,
        source_document_id=document.id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    session.commit()
    return asset, version, raw_object.uri, text_object.uri


def test_export_purge_is_policy_gated_hold_aware_and_idempotent(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    principal = _principal(session, tenant)
    store = FileSystemObjectStore(tmp_path / "objects")
    service = DataLifecycleService(session, store)
    job = _expired_job(session, tenant, store)
    artifact_uri = job.artifact_uri
    manifest_uri = job.manifest_uri

    with pytest.raises(LifecycleConflict, match="No active"):
        service.purge_export(
            principal,
            job.id,
            idempotency_key="purge-before-policy",
            reason="retention expired",
            request_id="request-1",
        )

    policy = service.upsert_export_policy(
        principal,
        retention_seconds=300,
        legal_basis="contractual retention schedule",
        geographic_scope=["CN"],
        active=True,
        request_id="request-2",
    )
    assert policy.policy_version == 1
    assert service.export_candidates(principal) == [job]

    hold = service.place_hold(
        principal,
        scope_type="data_export_job",
        scope_id=job.id,
        matter_reference="MATTER-2026-001",
        reason="preserve evidence for legal review",
        request_id="request-3",
    )
    blocked = service.purge_export(
        principal,
        job.id,
        idempotency_key="purge-blocked-1",
        reason="scheduled retention sweep",
        request_id="request-4",
    )
    assert blocked.event.outcome == "blocked"
    assert blocked.event.legal_hold_ids == [hold.id]
    assert store.read_bytes(artifact_uri or "", 1000)

    service.release_hold(
        principal,
        hold.id,
        reason="legal matter closed",
        request_id="request-5",
    )
    outcome = service.purge_export(
        principal,
        job.id,
        idempotency_key="purge-success-1",
        reason="approved retention deletion",
        request_id="request-6",
    )
    assert outcome.event.outcome == "succeeded"
    assert outcome.event.details["object_existed"] == {"artifact": "deleted", "manifest": "deleted"}
    assert job.state == "expired"
    assert job.artifact_uri is None
    assert job.manifest_uri is None
    assert artifact_uri is not None
    assert manifest_uri is not None
    assert not Path(artifact_uri.removeprefix("file://")).exists()
    assert not Path(manifest_uri.removeprefix("file://")).exists()

    replay = service.purge_export(
        principal,
        job.id,
        idempotency_key="purge-success-1",
        reason="approved retention deletion",
        request_id="request-7",
    )
    assert replay.replayed is True
    assert replay.event.id == outcome.event.id
    assert len(service.list_events(principal)) == 2


def test_shared_legacy_object_is_retained_until_last_reference(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    principal = _principal(session, tenant)
    store = FileSystemObjectStore(tmp_path / "objects")
    service = DataLifecycleService(session, store)
    first = _expired_job(session, tenant, store)
    shared_uri = first.artifact_uri
    second = DataExportJob(
        id="55555555-5555-4555-8555-555555555555",
        tenant_id=tenant.id,
        billing_account_id=first.billing_account_id,
        subscription_id=first.subscription_id,
        agent_client_id=first.agent_client_id,
        actor_type="agent",
        subject_id="agent-subject",
        idempotency_key="export-request-2",
        request_sha256="c" * 64,
        dataset="entities",
        license_policy_version="test-v1",
        license_policy_sha256="b" * 64,
        license_attribution="test",
        export_format="jsonl",
        filters_json={},
        fields_json=["id"],
        max_records=10,
        max_billable_units=Decimal("10"),
        state="completed",
        approval_required=False,
        workflow_id="data-export-shared-2",
        artifact_uri=first.artifact_uri,
        artifact_sha256=first.artifact_sha256,
        artifact_bytes=first.artifact_bytes,
        requested_at=first.requested_at,
        completed_at=first.completed_at,
        expires_at=first.expires_at,
    )
    session.add(second)
    session.commit()
    service.upsert_export_policy(
        principal,
        retention_seconds=300,
        legal_basis="contractual retention schedule",
        geographic_scope=["CN"],
        active=True,
        request_id="request-shared-policy",
    )

    outcome = service.purge_export(
        principal,
        first.id,
        idempotency_key="purge-shared-1",
        reason="approved retention deletion",
        request_id="request-shared-purge",
    )

    assert outcome.event.details["object_existed"]["artifact"] == "retained_shared_reference"
    assert store.read_bytes(shared_uri or "", 1000)


def test_source_purge_closes_dependencies_honors_holds_and_is_idempotent(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    principal = _principal(session, tenant)
    store = FileSystemObjectStore(tmp_path / "source-objects")
    service = DataLifecycleService(session, store)
    asset, version, raw_uri, text_uri = _missing_source_asset(session, tenant, store)
    service.upsert_source_policy(
        principal,
        retention_seconds=300,
        legal_basis="approved source withdrawal schedule",
        geographic_scope=["CN"],
        active=True,
        request_id="source-policy",
    )
    assert service.source_candidates(principal)[0].asset.id == asset.id

    hold = service.place_hold(
        principal,
        scope_type="source_asset",
        scope_id=asset.id,
        matter_reference="SOURCE-MATTER-1",
        reason="retain source during investigation",
        request_id="source-hold",
    )
    blocked = service.purge_source_asset(
        principal,
        asset.id,
        idempotency_key="source-purge-blocked",
        reason="scheduled source withdrawal",
        request_id="source-purge-blocked",
    )
    assert blocked.event.outcome == "blocked"
    assert blocked.event.details["blockers"] == ["legal_hold_active"]
    assert store.read_bytes(raw_uri, 1000)

    service.release_hold(principal, hold.id, reason="investigation closed", request_id="source-hold-release")
    outcome = service.purge_source_asset(
        principal,
        asset.id,
        idempotency_key="source-purge-success",
        reason="approved source withdrawal",
        request_id="source-purge-success",
    )
    assert outcome.event.outcome == "succeeded"
    assert outcome.event.details["deleted_objects"] == {
        f"raw:{version.id}": "deleted",
        f"text:{version.id}": "deleted",
    }
    session.refresh(asset)
    session.refresh(version)
    assert asset.state == SourceAssetState.DELETED
    assert asset.current_version_id is None
    assert version.raw_object_uri is None
    assert version.source_document_id is None
    with pytest.raises(FileNotFoundError):
        store.read_bytes(raw_uri, 1000)
    with pytest.raises(FileNotFoundError):
        store.read_bytes(text_uri, 1000)
    replay = service.purge_source_asset(
        principal,
        asset.id,
        idempotency_key="source-purge-success",
        reason="approved source withdrawal",
        request_id="source-purge-replay",
    )
    assert replay.replayed is True

    assert service.deleted_source_assets(principal) == [asset]
    with pytest.raises(LifecycleConflict, match="another lifecycle action"):
        service.reauthorize_source_asset(
            principal,
            asset.id,
            idempotency_key="source-purge-success",
            reason="restore source authorization",
            request_id="source-reauthorize-key-conflict",
        )

    reauthorization_hold = service.place_hold(
        principal,
        scope_type="source_asset",
        scope_id=asset.id,
        matter_reference="SOURCE-MATTER-2",
        reason="verify reauthorization governance",
        request_id="source-reauthorize-hold",
    )
    blocked_reauthorization = service.reauthorize_source_asset(
        principal,
        asset.id,
        idempotency_key="source-reauthorize-blocked",
        reason="restore source authorization",
        request_id="source-reauthorize-blocked",
    )
    assert blocked_reauthorization.event.action == "reauthorize"
    assert blocked_reauthorization.event.outcome == "blocked"
    session.refresh(asset)
    assert asset.state == SourceAssetState.DELETED

    service.release_hold(
        principal,
        reauthorization_hold.id,
        reason="reauthorization approved",
        request_id="source-reauthorize-hold-release",
    )
    reauthorized = service.reauthorize_source_asset(
        principal,
        asset.id,
        idempotency_key="source-reauthorize-success",
        reason="restore source authorization",
        request_id="source-reauthorize-success",
    )
    assert reauthorized.event.action == "reauthorize"
    assert reauthorized.event.outcome == "succeeded"
    assert reauthorized.event.details == {"next_state": "missing", "requires_rescan": True}
    reauthorized_asset = session.get(SourceAsset, asset.id, populate_existing=True)
    assert reauthorized_asset is not None
    assert reauthorized_asset.state == SourceAssetState.MISSING
    assert reauthorized_asset.current_version_id is None
    assert reauthorized_asset.source_fingerprint is None
    assert service.deleted_source_assets(principal) == []

    reauthorization_replay = service.reauthorize_source_asset(
        principal,
        asset.id,
        idempotency_key="source-reauthorize-success",
        reason="restore source authorization",
        request_id="source-reauthorize-replay",
    )
    assert reauthorization_replay.replayed is True
    assert reauthorization_replay.event.id == reauthorized.event.id


def test_source_purge_is_blocked_by_published_governed_facts(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    principal = _principal(session, tenant)
    store = FileSystemObjectStore(tmp_path / "published-objects")
    service = DataLifecycleService(session, store)
    asset, version, raw_uri, _ = _missing_source_asset(session, tenant, store, suffix="published")
    extraction = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="target",
        schema_version="1",
        model_provider="test",
        model_name="deterministic",
        prompt_sha256="a" * 64,
        policy_sha256="b" * 64,
        input_sha256=version.content_sha256,
        status=RunState.SUCCEEDED,
    )
    session.add(extraction)
    session.flush()
    session.add(
        StagedFact(
            tenant_id=tenant.id,
            extraction_run_id=extraction.id,
            fact_kind="target_profile",
            fact_key="EGFR",
            raw_payload={"name": "EGFR"},
            payload={"name": "EGFR"},
            source_quote="EGFR evidence",
            confidence=0.99,
            status=GovernanceStatus.PUBLISHED,
            published_resource_type="target_profile",
            published_resource_id="11111111-1111-4111-8111-111111111112",
        )
    )
    session.commit()
    service.upsert_source_policy(
        principal,
        retention_seconds=300,
        legal_basis="approved source withdrawal schedule",
        geographic_scope=["CN"],
        active=True,
        request_id="published-policy",
    )

    outcome = service.purge_source_asset(
        principal,
        asset.id,
        idempotency_key="published-source-purge",
        reason="scheduled source withdrawal",
        request_id="published-source-purge",
    )

    assert outcome.event.outcome == "blocked"
    assert outcome.event.details["blockers"] == ["published_facts"]
    assert store.read_bytes(raw_uri, 1000)
    session.refresh(asset)
    assert asset.state == SourceAssetState.MISSING


def test_source_purge_is_blocked_by_another_extraction_run_document_reference(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    principal = _principal(session, tenant)
    store = FileSystemObjectStore(tmp_path / "cross-reference-objects")
    service = DataLifecycleService(session, store)
    asset, version, raw_uri, _ = _missing_source_asset(session, tenant, store, suffix="withdrawn")
    _, other_version, _, _ = _missing_source_asset(session, tenant, store, suffix="other")
    external_run = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=other_version.id,
        schema_name="target",
        schema_version="1",
        model_provider="test",
        model_name="deterministic",
        prompt_sha256="c" * 64,
        policy_sha256="d" * 64,
        input_sha256=other_version.content_sha256,
        status=RunState.SUCCEEDED,
    )
    session.add(external_run)
    session.flush()
    session.add(
        StagedFact(
            tenant_id=tenant.id,
            extraction_run_id=external_run.id,
            fact_kind="target_profile",
            fact_key="EGFR-cross-reference",
            raw_payload={"name": "EGFR"},
            payload={"name": "EGFR"},
            source_document_id=version.source_document_id,
            source_quote="Cross-referenced EGFR evidence",
            confidence=0.8,
            status=GovernanceStatus.PROPOSED,
        )
    )
    session.commit()
    service.upsert_source_policy(
        principal,
        retention_seconds=300,
        legal_basis="approved source withdrawal schedule",
        geographic_scope=["CN"],
        active=True,
        request_id="cross-reference-policy",
    )

    outcome = service.purge_source_asset(
        principal,
        asset.id,
        idempotency_key="cross-reference-purge",
        reason="scheduled source withdrawal",
        request_id="cross-reference-purge",
    )

    assert outcome.event.outcome == "blocked"
    assert outcome.event.details["blockers"] == ["other_source_document_references"]
    assert store.read_bytes(raw_uri, 1000)
