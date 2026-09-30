from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from pharma_intel.commercial.admin import CommercialAdminService, ProvisionClientCommand
from pharma_intel.commercial.exports import build_export_service, default_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.config import Settings, get_settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance.service import SCHEMA_NAME, SCHEMA_VERSION, governance_policy_sha256
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    ActivityMeasurement,
    ApiKey,
    Assay,
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    MeasurementRelation,
    ReviewStatus,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
    TenantDataset,
    UsageSettlement,
    User,
    UserRole,
)
from pharma_intel.security import hash_password, issue_api_key, normalize_email

try:
    from scripts.mcp_anti_extraction_probe import (
        MCP_PROTOCOL_BASELINE,
        _available_port,
        _call_tool,
        _create_database,
        _drop_database,
        _local_database_credentials,
        _migrate_database,
        _runtime_url,
        _service_environment,
        _start_service,
        _stop_process,
        _wait_for_api,
        _wait_for_mcp,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from mcp_anti_extraction_probe import (  # type: ignore[no-redef,import-not-found]
        MCP_PROTOCOL_BASELINE,
        _available_port,
        _call_tool,
        _create_database,
        _drop_database,
        _local_database_credentials,
        _migrate_database,
        _runtime_url,
        _service_environment,
        _start_service,
        _stop_process,
        _wait_for_api,
        _wait_for_mcp,
    )

OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATABASE_NAME = re.compile(r"^pharma_record_consistency_[0-9a-f]{12}$")
ACTIVITY_FIELDS = (
    "id",
    "compound_entity_id",
    "target_entity_id",
    "assay_id",
    "standard_type",
    "standard_relation",
    "standard_value",
    "standard_units",
    "reported_type",
    "reported_relation",
    "reported_value",
    "reported_units",
    "source_system",
    "source_activity_id",
    "source_document_id",
)
PROVENANCE_FIELDS = (
    "id",
    "resource_type",
    "resource_id",
    "dataset_key",
    "evidence_claim_id",
    "source_document_id",
    "source_version_id",
    "content_sha256",
    "locator",
    "quote",
)
EXPORT_FIELDS = (
    "id",
    "resource_type",
    "resource_id",
    "evidence_claim_id",
    "source_asset_id",
    "source_version_id",
    "source_document_id",
    "dataset_key",
    "source_locator",
    "created_at",
)


@dataclass(frozen=True)
class Fixture:
    tenant_id: str
    token: str
    admin_email: str
    admin_password: str
    target_id: str
    activity_id: str
    provenance_id: str
    evidence_claim_id: str
    source_asset_id: str
    source_version_id: str
    source_document_id: str
    source_locator: str
    content_sha256: str


def _seed_fixture(database_url: URL) -> Fixture:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="record-consistency-acceptance", name="Record Consistency Acceptance")
            session.add(tenant)
            session.flush()
            set_tenant_context(session, tenant.id)

            admin_email = "record-consistency-admin@example.invalid"
            admin_password = secrets.token_urlsafe(32)
            session.add(
                User(
                    tenant_id=tenant.id,
                    email=admin_email,
                    normalized_email=normalize_email(admin_email),
                    display_name="Record Consistency Operator",
                    password_hash=hash_password(admin_password),
                    role=UserRole.ADMIN,
                )
            )
            token, token_hash = issue_api_key()
            api_key = ApiKey(
                tenant_id=tenant.id,
                name="record-consistency-agent",
                prefix=token[:12],
                secret_hash=token_hash,
                scopes=["mcp:connect", "activities:read", "evidence:read", "data:export"],
            )
            session.add(api_key)
            session.flush()

            admin = CommercialAdminService(session, tenant, actor_id="isolated-record-consistency")
            card = admin.publish_rate_card(
                RateCardDefinition.model_validate(
                    {
                        "rate_card_key": "record-consistency-plan",
                        "revision": 1,
                        "currency": "CNY",
                        "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                        "items": [
                            {
                                "billing_class": "bioactivity.search",
                                "entitlement_key": "activities.read",
                                "base_units": "1",
                                "per_result_units": "0.01",
                                "per_kib_units": "0.001",
                                "per_compute_unit": "0",
                                "max_result_rows": 500,
                            },
                            {
                                "billing_class": "provenance.read",
                                "entitlement_key": "evidence.read",
                                "base_units": "1",
                                "per_result_units": "0.01",
                                "per_kib_units": "0.001",
                                "per_compute_unit": "0",
                                "max_result_rows": 100,
                            },
                            {
                                "billing_class": "export.data",
                                "entitlement_key": "data.export",
                                "base_units": "2",
                                "per_result_units": "0.02",
                                "per_kib_units": "0.001",
                                "per_compute_unit": "0",
                                "max_result_rows": 5000,
                            },
                        ],
                    }
                )
            )
            subscription = admin.provision_client(
                ProvisionClientCommand(
                    client_key="record-consistency-agent",
                    oauth_client_id=api_key.id,
                    display_name="Record Consistency Agent",
                    actor_type="api_key",
                    subject_id=api_key.id,
                    account_key="record-consistency-account",
                    account_name="Record Consistency Account",
                    subscription_key="record-consistency-subscription",
                    rate_card_key=card.rate_card_key,
                    rate_card_revision=card.revision,
                    created_by="isolated-record-consistency",
                    export_field_policy=default_export_field_policy(
                        policy_version="record-consistency-export-v1",
                        attribution="Isolated acceptance fixture",
                    ),
                )
            )
            admin.grant_credit(
                subscription.subscription_key,
                Decimal("1000"),
                external_reference="record-consistency-credit",
                reason="isolated record consistency acceptance",
            )

            dataset = TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                required_scopes=["evidence:read"],
                license_policy=internal_evidence_license_policy(source="record-consistency-acceptance"),
            )
            source = DataSource(
                tenant_id=tenant.id,
                name="Record consistency source",
                source_type=DataSourceType.FOLDER,
                root_uri="/record-consistency-source",
                owner="Acceptance Operations",
                authorization_scopes=["contract:record-consistency"],
                dataset_key=dataset.dataset_key,
            )
            target = Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.TARGET,
                name="EGFR acceptance target",
                normalized_name="egfr acceptance target",
                review_status=ReviewStatus.VERIFIED,
            )
            compound = Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.DRUG,
                name="Acceptance compound A",
                normalized_name="acceptance compound a",
                review_status=ReviewStatus.VERIFIED,
            )
            session.add_all([dataset, source, target, compound])
            session.flush()

            content_sha256 = "a" * 64
            source_locator = "page=7;paragraph=2"
            asset = SourceAsset(
                tenant_id=tenant.id,
                data_source_id=source.id,
                logical_path="egfr-activity.pdf",
                source_uri="file:///record-consistency-source/egfr-activity.pdf",
                file_name="egfr-activity.pdf",
                extension=".pdf",
                processing_mode="parse",
            )
            document = SourceDocument(
                tenant_id=tenant.id,
                title="EGFR activity acceptance source",
                source_type="folder",
                source_uri=asset.source_uri,
                content_sha256=content_sha256,
            )
            session.add_all([asset, document])
            session.flush()
            version = SourceVersion(
                tenant_id=tenant.id,
                source_asset_id=asset.id,
                version_number=1,
                content_sha256=content_sha256,
                size_bytes=2048,
                source_document_id=document.id,
            )
            session.add(version)
            session.flush()
            extraction = ExtractionRun(
                tenant_id=tenant.id,
                source_version_id=version.id,
                schema_name=SCHEMA_NAME,
                schema_version=SCHEMA_VERSION,
                model_provider="controlled-acceptance",
                model_name="deterministic-fixture",
                prompt_sha256="b" * 64,
                policy_sha256=governance_policy_sha256(get_settings()),
                input_sha256="c" * 64,
                status=RunState.SUCCEEDED,
            )
            session.add(extraction)
            session.flush()
            staged = StagedFact(
                tenant_id=tenant.id,
                extraction_run_id=extraction.id,
                fact_kind="activity",
                fact_key="egfr-acceptance-activity",
                raw_payload={"reported_value": "12"},
                payload={"reported_value": "12", "standard_value": 12.0},
                source_document_id=document.id,
                source_locator=source_locator,
                source_quote="EGFR biochemical activity was 12 nM.",
                confidence=0.99,
                status=GovernanceStatus.PUBLISHED,
            )
            assay = Assay(
                tenant_id=tenant.id,
                source_system="controlled_acceptance",
                source_assay_id="egfr-biochemical-assay",
                target_entity_id=target.id,
                assay_type="binding",
                description="EGFR biochemical binding assay",
                source_document_id=document.id,
            )
            session.add_all([staged, assay])
            session.flush()
            activity = ActivityMeasurement(
                tenant_id=tenant.id,
                source_system="controlled_acceptance",
                source_activity_id="egfr-activity-12nm",
                assay_id=assay.id,
                compound_entity_id=compound.id,
                target_entity_id=target.id,
                reported_type="IC50",
                reported_relation=MeasurementRelation.EQUAL,
                reported_value="12",
                reported_units="nM",
                standard_type="IC50",
                standard_relation=MeasurementRelation.EQUAL,
                standard_value=12.0,
                standard_units="nM",
                pchembl_value=7.92,
                qualifiers={"acceptance_fixture": True},
            )
            claim = EvidenceClaim(
                tenant_id=tenant.id,
                subject_id=target.id,
                predicate="has_activity",
                value={"standard_type": "IC50", "standard_value": 12.0, "standard_units": "nM"},
                source_document_id=document.id,
                source_locator=source_locator,
                quote=staged.source_quote,
                confidence=staged.confidence,
                review_status=ReviewStatus.VERIFIED,
            )
            session.add_all([activity, claim])
            session.flush()
            link = FactProvenanceLink(
                tenant_id=tenant.id,
                resource_type="activity_measurement",
                resource_id=activity.id,
                staged_fact_id=staged.id,
                evidence_claim_id=claim.id,
                source_asset_id=asset.id,
                source_version_id=version.id,
                source_document_id=document.id,
                dataset_key=dataset.dataset_key,
                source_locator=source_locator,
            )
            session.add(link)
            session.commit()
            return Fixture(
                tenant_id=tenant.id,
                token=token,
                admin_email=admin_email,
                admin_password=admin_password,
                target_id=target.id,
                activity_id=activity.id,
                provenance_id=link.id,
                evidence_claim_id=claim.id,
                source_asset_id=asset.id,
                source_version_id=version.id,
                source_document_id=document.id,
                source_locator=source_locator,
                content_sha256=content_sha256,
            )
    finally:
        engine.dispose()


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} returned a non-object payload")
    return value


def _canonical(value: object, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    document = _object(value, label)
    missing = [field for field in fields if field not in document]
    if missing:
        raise RuntimeError(f"{label} omitted fields: {missing}")
    return {field: document[field] for field in fields}


def _same(left: object, right: object, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    left_canonical = _canonical(left, fields, f"{label} left")
    right_canonical = _canonical(right, fields, f"{label} right")
    changed = [field for field in fields if left_canonical[field] != right_canonical[field]]
    if changed:
        raise RuntimeError(f"{label} drifted fields: {changed}")
    return left_canonical


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _execute_export(runtime_url: URL, tenant_id: str, job_id: str, work: Path) -> dict[str, Any]:
    settings = Settings(
        app_env="development",
        database_url=runtime_url.render_as_string(hide_password=False),
        object_store_root=work / "object-store",
        markdown_export_root=work / "markdown-wiki",
    )
    engine = create_engine(runtime_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            set_tenant_context(
                session,
                tenant_id,
                signing_secret=settings.effective_tenant_context_signing_secret,
            )
            job = build_export_service(session, settings).execute(tenant_id, job_id)
            if not job.reservation_id:
                raise RuntimeError("Completed export omitted its reservation")
            settlement = session.scalar(
                select(UsageSettlement).where(
                    UsageSettlement.tenant_id == tenant_id,
                    UsageSettlement.reservation_id == job.reservation_id,
                )
            )
            if settlement is None:
                raise RuntimeError("Completed export omitted its settlement")
            return {"state": job.state, "settlement_id": settlement.id}
    finally:
        engine.dispose()


async def _exercise(
    api_url: str,
    mcp_url: str,
    runtime_url: URL,
    fixture: Fixture,
    work: Path,
) -> dict[str, Any]:
    timeout = httpx.Timeout(30, connect=10)
    async with httpx.AsyncClient(base_url=api_url, timeout=timeout, trust_env=False) as web:
        login = await web.post(
            "/api/v1/auth/login",
            json={"email": fixture.admin_email, "password": fixture.admin_password},
        )
        if login.status_code != 200:
            raise RuntimeError(f"Isolated Web login returned HTTP {login.status_code}")
        web_activity_response = await web.get(
            f"/api/v1/targets/{fixture.target_id}/bioactivities",
            params={"limit": 10, "offset": 0},
        )
        if web_activity_response.status_code != 200:
            raise RuntimeError(f"Web bioactivity read returned HTTP {web_activity_response.status_code}")
        web_activities = web_activity_response.json()
        if not isinstance(web_activities, list):
            raise RuntimeError("Web bioactivity read omitted its list")
        web_activity = next(
            (item for item in web_activities if isinstance(item, dict) and item.get("id") == fixture.activity_id),
            None,
        )
        if web_activity is None:
            raise RuntimeError("Web bioactivity read did not return the fixture")
        web_provenance_response = await web.get(
            f"/api/v1/provenance/activity_measurement/{fixture.activity_id}",
            params={"limit": 10},
        )
        if web_provenance_response.status_code != 200:
            raise RuntimeError(f"Web provenance read returned HTTP {web_provenance_response.status_code}")
        web_provenance_payload = _object(web_provenance_response.json(), "Web provenance")
        web_provenance_items = web_provenance_payload.get("items")
        if not isinstance(web_provenance_items, list) or len(web_provenance_items) != 1:
            raise RuntimeError("Web provenance did not return exactly one fixture link")
        web_provenance = _object(web_provenance_items[0], "Web provenance item")

    activity_result = await _call_tool(
        mcp_url,
        fixture.token,
        "get_bioactivity_landscape",
        {
            "target_entity_id": fixture.target_id,
            "standard_type": "IC50",
            "limit": 10,
            "idempotency_key": f"record-consistency-activity-{secrets.token_hex(10)}",
            "max_billable_units": "100",
        },
    )
    activity_data = _object(activity_result.get("data"), "MCP bioactivity data")
    activity_usage = _object(activity_result.get("usage"), "MCP bioactivity usage")
    mcp_activity_items = activity_data.get("items")
    if not isinstance(mcp_activity_items, list):
        raise RuntimeError("MCP bioactivity omitted items")
    mcp_activity = next(
        (item for item in mcp_activity_items if isinstance(item, dict) and item.get("id") == fixture.activity_id),
        None,
    )
    if mcp_activity is None:
        raise RuntimeError("MCP bioactivity did not return the fixture")
    canonical_activity = _same(web_activity, mcp_activity, ACTIVITY_FIELDS, "Web/MCP activity")

    provenance_result = await _call_tool(
        mcp_url,
        fixture.token,
        "get_record_provenance",
        {
            "resource_type": "activity_measurement",
            "resource_id": fixture.activity_id,
            "limit": 10,
            "idempotency_key": f"record-consistency-provenance-{secrets.token_hex(10)}",
            "max_billable_units": "100",
        },
    )
    provenance_data = _object(provenance_result.get("data"), "MCP provenance data")
    provenance_usage = _object(provenance_result.get("usage"), "MCP provenance usage")
    mcp_provenance_items = provenance_data.get("items")
    if not isinstance(mcp_provenance_items, list) or len(mcp_provenance_items) != 1:
        raise RuntimeError("MCP provenance did not return exactly one fixture link")
    canonical_provenance = _same(
        web_provenance,
        mcp_provenance_items[0],
        PROVENANCE_FIELDS,
        "Web/MCP provenance",
    )

    export_created = await _call_tool(
        mcp_url,
        fixture.token,
        "create_data_export",
        {
            "dataset": "fact_provenance",
            "export_format": "jsonl",
            "filters": {"resource_id": fixture.activity_id},
            "fields": list(EXPORT_FIELDS),
            "max_records": 10,
            "idempotency_key": f"record-consistency-export-{secrets.token_hex(10)}",
            "max_billable_units": "100",
        },
    )
    job_id = export_created.get("id")
    if not isinstance(job_id, str) or export_created.get("state") != "queued":
        raise RuntimeError("MCP export was not queued without manual approval")
    export_execution = await asyncio.to_thread(_execute_export, runtime_url, fixture.tenant_id, job_id, work)
    if export_execution.get("state") != "completed":
        raise RuntimeError("Isolated export execution did not complete")
    export_status = await _call_tool(mcp_url, fixture.token, "get_data_export", {"job_id": job_id})
    if (
        export_status.get("state") != "completed"
        or export_status.get("record_count") != 1
        or export_status.get("artifact_sha256") is None
        or export_status.get("manifest_signature") is None
    ):
        raise RuntimeError("MCP export status omitted completed signed artifact metadata")
    export_chunk = await _call_tool(
        mcp_url,
        fixture.token,
        "read_data_export",
        {"job_id": job_id, "limit": 10},
    )
    export_items = export_chunk.get("items")
    if not isinstance(export_items, list) or len(export_items) != 1:
        raise RuntimeError("MCP export chunk did not contain exactly one provenance row")
    export_row = _canonical(export_items[0], EXPORT_FIELDS, "MCP provenance export")
    manifest = _object(export_chunk.get("manifest"), "MCP export manifest")
    manifest_payload = _object(manifest.get("payload"), "MCP export manifest payload")
    if (
        manifest.get("schema") != "pharma.data-export-envelope.v1"
        or manifest_payload.get("dataset") != "fact_provenance"
        or manifest_payload.get("record_count") != 1
        or manifest_payload.get("authority") != "PostgreSQL tenant authority store"
    ):
        raise RuntimeError("MCP export manifest is not bound to the authority dataset")

    expected_source = {
        "resource_type": "activity_measurement",
        "resource_id": fixture.activity_id,
        "evidence_claim_id": fixture.evidence_claim_id,
        "source_document_id": fixture.source_document_id,
        "source_version_id": fixture.source_version_id,
        "dataset_key": "literature",
    }
    provenance_source = {key: canonical_provenance[key] for key in expected_source}
    export_source = {key: export_row[key] for key in expected_source}
    if provenance_source != expected_source or export_source != expected_source:
        raise RuntimeError("Web/MCP/export authority identifiers are inconsistent")
    if (
        canonical_provenance["locator"] != fixture.source_locator
        or export_row["source_locator"] != fixture.source_locator
    ):
        raise RuntimeError("Web/MCP/export source locators are inconsistent")
    if canonical_provenance["content_sha256"] != fixture.content_sha256:
        raise RuntimeError("Provenance content digest drifted from the source version")

    settlement_ids = [
        activity_usage.get("settlement_id"),
        provenance_usage.get("settlement_id"),
        export_execution.get("settlement_id"),
    ]
    if any(not isinstance(value, str) for value in settlement_ids) or len(set(settlement_ids)) != 3:
        raise RuntimeError("Record consistency operations did not create three unique settlements")
    return {
        "activity_id": fixture.activity_id,
        "target_id": fixture.target_id,
        "provenance_id": fixture.provenance_id,
        "source_version_id": fixture.source_version_id,
        "source_document_id": fixture.source_document_id,
        "source_locator": fixture.source_locator,
        "activity_sha256": _sha256(canonical_activity),
        "provenance_sha256": _sha256(canonical_provenance),
        "export_row_sha256": _sha256(export_row),
        "web_operations": ["get_bioactivities", "get_record_provenance"],
        "mcp_tools": [
            "get_bioactivity_landscape",
            "get_record_provenance",
            "create_data_export",
            "get_data_export",
            "read_data_export",
        ],
        "mcp_protocol_version": MCP_PROTOCOL_BASELINE,
        "billed_operations": 3,
        "unique_settlements": 3,
        "export_dataset": "fact_provenance",
        "export_record_count": 1,
        "export_manifest_verified": True,
        "same_authority_identifiers": True,
        "same_source_version": True,
        "same_source_locator": True,
    }


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    if not OUTPUT_NAME.fullmatch(path.name):
        raise ValueError("Output filename contains unsupported characters")
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = path.parent.resolve()
    resolved = resolved_parent / path.name
    if resolved.exists() or resolved.is_symlink():
        raise FileExistsError(f"Refusing to overwrite record consistency evidence: {resolved}")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, resolved, follow_symlinks=False)
        except FileExistsError as exc:
            raise FileExistsError(f"Refusing to overwrite record consistency evidence: {resolved}") from exc
        directory_fd = os.open(resolved_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def execute(output: Path) -> dict[str, Any]:
    if get_settings().app_env.casefold() == "production":
        raise RuntimeError("The isolated record consistency probe cannot run with APP_ENV=production")
    credentials = _local_database_credentials()
    database_name = f"pharma_record_consistency_{secrets.token_hex(6)}"
    if not DATABASE_NAME.fullmatch(database_name):
        raise RuntimeError("Generated record consistency database name is unsafe")
    database_dropped = False
    api_stopped = False
    mcp_stopped = False
    api_process: subprocess.Popen[bytes] | None = None
    mcp_process: subprocess.Popen[bytes] | None = None
    secret_values: list[str] = []
    result: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="pharma-record-consistency-") as temporary:
        work = Path(temporary)
        admin_target = _create_database(
            credentials.admin_url,
            database_name,
            database_name_pattern=DATABASE_NAME,
        )
        try:
            _migrate_database(admin_target, credentials.runtime_password, work)
            fixture = _seed_fixture(admin_target)
            secret_values.extend([fixture.token, fixture.admin_password])
            runtime_url = _runtime_url(admin_target, credentials)
            gateway_port = _available_port()
            environment = _service_environment(runtime_url, gateway_port, gateway_port, work)
            api_process = _start_service("pharma-gateway", environment, work / "gateway.log")
            mcp_process = api_process
            api_url = f"http://127.0.0.1:{gateway_port}"
            _wait_for_api(api_url, api_process)
            mcp_url = f"http://127.0.0.1:{gateway_port}/mcp"
            _wait_for_mcp(mcp_url, fixture.token, mcp_process)
            result = asyncio.run(_exercise(api_url, mcp_url, runtime_url, fixture, work))
        finally:
            mcp_stopped = _stop_process(mcp_process)
            api_stopped = _stop_process(api_process)
            _drop_database(
                credentials.admin_url,
                database_name,
                database_name_pattern=DATABASE_NAME,
            )
            database_dropped = True

    if result is None:
        raise RuntimeError("Record consistency probe did not produce a result")
    report = {
        "schema": "pharma.record-consistency-acceptance.v1",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        **result,
        "cleanup": {
            "api_stopped": api_stopped,
            "mcp_stopped": mcp_stopped,
            "database_dropped": database_dropped,
        },
    }
    serialized = json.dumps(report, sort_keys=True)
    if any(secret in serialized for secret in secret_values):
        raise RuntimeError("Record consistency evidence contains a generated credential")
    if not all(report["cleanup"].values()):
        raise RuntimeError("Record consistency cleanup did not complete")
    _atomic_write(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify one authoritative pharmaceutical fact across Web, billed MCP and governed export"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.output)
    print(
        "RECORD_CONSISTENCY "
        f"status={report['status']} billed_operations={report['billed_operations']} "
        f"database_dropped={str(report['cleanup']['database_dropped']).lower()} "
        "credentials_recorded=false production_claim=false"
    )
    print(f"record_consistency_report={args.output.resolve()}")


if __name__ == "__main__":
    main()
