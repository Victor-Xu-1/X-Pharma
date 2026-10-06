from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings, get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.ingest.connectors import SourceConnectorRegistry
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.ingest.public_sources import (
    register_chembl_source as register_chembl_source,
)
from pharma_intel.ingest.public_sources import (
    register_clinicaltrials_gov_source as register_clinicaltrials_gov_source,
)
from pharma_intel.ingest.public_sources import (
    register_pubmed_source as register_pubmed_source,
)
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.models import DataSource, DataSourceState, DataSourceType, Tenant
from pharma_intel.object_store import build_object_store

logger = logging.getLogger(__name__)


def collect_ingestion_readiness(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> dict[str, Any]:
    effective_settings = settings or get_settings()
    effective_session_factory = session_factory or get_session_factory()
    registry = SourceConnectorRegistry(effective_settings)
    generated_at = datetime.now(UTC)
    runtime_checks = [
        {
            "code": "temporal_enabled",
            "status": "pass" if effective_settings.temporal_enabled else "fail",
        },
        {
            "code": "temporal_worker_enabled",
            "status": "pass" if effective_settings.temporal_worker_enabled else "fail",
        },
        {
            "code": "temporal_scheduler_enabled",
            "status": "pass" if effective_settings.temporal_scheduler_enabled else "fail",
        },
        {
            "code": "source_roots_configured",
            "status": "pass" if effective_settings.source_roots else "fail",
        },
        {
            "code": "malware_scan_enabled",
            "status": "pass" if effective_settings.malware_scan_enabled else "fail",
        },
        {
            "code": "isolated_parser_configured",
            "status": "pass" if effective_settings.parser_backend == "service" else "fail",
        },
    ]
    connectors = []
    for source_type in DataSourceType:
        capabilities = registry.capabilities(source_type)
        connectors.append(
            {
                "source_type": source_type.value,
                "connector_id": capabilities.connector_id,
                "incremental": capabilities.incremental,
                "replayable": capabilities.replayable,
                "credentials_required": capabilities.credentials_required,
                "immutable_snapshot_required": capabilities.immutable_snapshot_required,
            }
        )

    sources: list[dict[str, object]] = []
    tenant_count = 0
    with effective_session_factory() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    for tenant_id in tenant_ids:
        tenant_count += 1
        with effective_session_factory() as session:
            set_tenant_context(session, tenant_id)
            tenant_sources = list(
                session.scalars(select(DataSource).where(DataSource.tenant_id == tenant_id).order_by(DataSource.id))
            )
            readiness_service = SourceReadinessService(
                session,
                effective_settings,
                tenant_id,
                connector_registry=registry,
            )
            for source in tenant_sources:
                readiness = readiness_service.evaluate(source, now=generated_at)
                sources.append(
                    {
                        "source_ref": hashlib.sha256(f"source:{source.id}".encode()).hexdigest()[:16],
                        "source_type": source.source_type.value,
                        "source_state": source.state.value,
                        "configuration_ready": readiness.configuration_ready,
                        "operational_status": readiness.operational_status,
                        "connector_id": readiness.connector_id,
                        "incremental": readiness.incremental,
                        "replayable": readiness.replayable,
                        "delivery_channels": readiness.delivery_channels,
                        "cursor_present": readiness.cursor_present,
                        "checks": [{"code": check.code, "status": check.status} for check in readiness.checks],
                    }
                )

    blocked_sources = sum(not bool(source["configuration_ready"]) for source in sources)
    runtime_failures = sum(check["status"] == "fail" for check in runtime_checks)
    if runtime_failures or blocked_sources:
        status = "blocked"
    elif not sources:
        status = "ready_for_source_registration"
    else:
        status = "ready_for_ingestion"
    return {
        "schema": "pharma.ingestion-readiness.v1",
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "status": status,
        "production_claim": False,
        "real_source_automatic_ingestion_verified": False,
        "runtime": {
            "checks": runtime_checks,
            "object_store_backend": effective_settings.object_store_backend,
            "parser_backend": effective_settings.parser_backend,
            "source_root_count": len(effective_settings.source_roots),
        },
        "connectors": connectors,
        "inventory": {
            "active_tenant_count": tenant_count,
            "registered_source_count": len(sources),
            "configuration_ready_source_count": len(sources) - blocked_sources,
            "blocked_source_count": blocked_sources,
        },
        "sources": sources,
    }


def inspect_source(source: DataSource, settings: Settings | None = None) -> dict[str, object]:
    effective_settings = settings or get_settings()
    registry = SourceConnectorRegistry(effective_settings)
    connector = registry.get(source.source_type)
    configuration_errors = connector.validate_configuration(source)
    if configuration_errors:
        return {
            "schema_version": 1,
            "source_id": source.id,
            "source_type": source.source_type.value,
            "connector_id": connector.capabilities.connector_id,
            "authoritative_inventory": False,
            "discovered": 0,
            "stable": 0,
            "oversized": 0,
            "excluded": 0,
            "error_count": 0,
            "configuration_error_count": len(configuration_errors),
        }
    discovery = connector.discover(source)
    stable_before = datetime.now(UTC) - timedelta(seconds=source.stable_seconds)
    stable = sum(
        1
        for item in discovery.objects
        if item.modified_at.astimezone(UTC) <= stable_before and item.size_bytes <= source.max_file_bytes
    )
    oversized = sum(1 for item in discovery.objects if item.size_bytes > source.max_file_bytes)
    return {
        "schema_version": 1,
        "source_id": source.id,
        "source_type": source.source_type.value,
        "connector_id": connector.capabilities.connector_id,
        "authoritative_inventory": discovery.authoritative_inventory,
        "discovered": len(discovery.objects),
        "stable": stable,
        "oversized": oversized,
        "excluded": discovery.excluded_count,
        "error_count": len(discovery.errors),
        "configuration_error_count": 0,
    }


def inspect_registered_source(source_id: str) -> dict[str, object]:
    settings = get_settings()
    matches: list[DataSource] = []
    with get_session_factory()() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    for tenant_id in tenant_ids:
        with get_session_factory()() as session:
            set_tenant_context(session, tenant_id)
            source = session.scalar(
                select(DataSource).where(
                    DataSource.id == source_id,
                    DataSource.tenant_id == tenant_id,
                    DataSource.state.in_([DataSourceState.ACTIVE, DataSourceState.UNAVAILABLE]),
                )
            )
            if source is not None:
                matches.append(source)
    if len(matches) != 1:
        raise ValueError("Eligible registered source was not found exactly once")
    return inspect_source(matches[0], settings)


def scan_registered_sources(source_id: str | None = None, *, process_versions: bool = True) -> dict[str, int]:
    settings = get_settings()
    totals = {"sources": 0, "versions": 0, "failed_sources": 0, "failed_versions": 0}
    with get_session_factory()() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    for tenant_id in tenant_ids:
        with get_session_factory()() as session:
            set_tenant_context(session, tenant_id)
            statement = select(DataSource).where(
                DataSource.tenant_id == tenant_id,
                DataSource.state.in_([DataSourceState.ACTIVE, DataSourceState.UNAVAILABLE]),
            )
            if source_id:
                statement = statement.where(DataSource.id == source_id)
            sources = list(session.scalars(statement.order_by(DataSource.name)))
        for source in sources:
            totals["sources"] += 1
            workflow_id = f"local-scan-{source.id}-{uuid.uuid4()}"
            try:
                with get_session_factory()() as session:
                    service = DataFactoryService(
                        session,
                        settings,
                        build_object_store(settings),
                        tenant_id,
                    )
                    scan = service.scan_source(source.id, workflow_id)
                    totals["versions"] += len(scan.version_ids)
                    if scan.state in {"failed", "partial"}:
                        totals["failed_sources"] += 1
                    if process_versions:
                        for version_id in scan.version_ids:
                            try:
                                result = service.process_version(version_id, from_stage="auto")
                            except Exception:
                                totals["failed_versions"] += 1
                                logger.exception(
                                    "registered_source_version_failed",
                                    extra={"source_id": source.id, "source_version_id": version_id},
                                )
                                continue
                            if result.error:
                                totals["failed_versions"] += 1
            except Exception:
                totals["failed_sources"] += 1
                logger.exception("registered_source_scan_failed", extra={"source_id": source.id})
    return totals


def run() -> None:
    parser = argparse.ArgumentParser(description="Automatic governed pharmaceutical data factory")
    parser.add_argument(
        "mode",
        choices=[
            "inspect",
            "once",
            "readiness",
            "register-clinicaltrials-gov",
            "register-pubmed",
            "register-chembl",
            "snapshot",
            "watch",
        ],
        nargs="?",
        default="once",
    )
    parser.add_argument("--source-id")
    parser.add_argument("--tenant-slug", default="default")
    parser.add_argument("--query-term")
    parser.add_argument("--target-chembl-id")
    parser.add_argument("--sync-mode", choices=["snapshot", "continuous"], default="snapshot")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--scan-interval-seconds", type=int, default=86_400)
    parser.add_argument("--include-abstract", action="store_true")
    parser.add_argument("--include-activities", action="store_true")
    parser.add_argument("--activity-limit", type=int, default=10)
    args = parser.parse_args()
    if args.mode != "register-chembl" and (args.include_activities or args.activity_limit != 10):
        parser.error("Activity enrichment flags require register-chembl")
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    if args.mode == "readiness":
        if args.source_id:
            parser.error("readiness does not accept --source-id")
        readiness = collect_ingestion_readiness(settings)
        print(json.dumps(readiness, sort_keys=True))
        if readiness["status"] == "blocked":
            raise SystemExit(1)
        return
    if args.mode == "inspect":
        if not args.source_id:
            parser.error("inspect requires --source-id")
        try:
            inspection = inspect_registered_source(args.source_id)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(inspection, sort_keys=True))
        if inspection["configuration_error_count"] or inspection["error_count"]:
            raise SystemExit(1)
        return
    if args.mode == "register-clinicaltrials-gov":
        if not args.query_term:
            parser.error("register-clinicaltrials-gov requires --query-term")
        if args.source_id:
            parser.error("register-clinicaltrials-gov does not accept --source-id")
        try:
            source = register_clinicaltrials_gov_source(
                tenant_slug=args.tenant_slug,
                query_term=args.query_term,
                max_records=args.max_records,
                page_size=args.page_size,
                scan_interval_seconds=args.scan_interval_seconds,
                sync_mode=args.sync_mode,
                start_date=args.start_date,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"source_id": source.id, "source_type": source.source_type.value}, sort_keys=True))
        return
    if args.mode == "register-pubmed":
        if not args.query_term:
            parser.error("register-pubmed requires --query-term")
        if args.sync_mode != "snapshot" or args.start_date is not None:
            parser.error("PubMed supports bounded metadata snapshots, not the continuous date-window contract")
        if args.source_id:
            parser.error("register-pubmed does not accept --source-id")
        try:
            source = register_pubmed_source(
                tenant_slug=args.tenant_slug,
                query_term=args.query_term,
                max_records=args.max_records,
                page_size=args.page_size,
                include_abstract=args.include_abstract,
                scan_interval_seconds=args.scan_interval_seconds,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"source_id": source.id, "source_type": source.source_type.value}, sort_keys=True))
        return
    if args.mode == "register-chembl":
        if not args.target_chembl_id:
            parser.error("register-chembl requires --target-chembl-id")
        if args.start_date is not None:
            parser.error("ChEMBL mechanism synchronization does not use --start-date")
        if args.source_id:
            parser.error("register-chembl does not accept --source-id")
        try:
            source = register_chembl_source(
                tenant_slug=args.tenant_slug,
                target_chembl_id=args.target_chembl_id,
                max_records=args.max_records,
                page_size=args.page_size,
                scan_interval_seconds=args.scan_interval_seconds,
                sync_mode=args.sync_mode,
                include_activities=args.include_activities,
                activity_limit=args.activity_limit,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"source_id": source.id, "source_type": source.source_type.value}, sort_keys=True))
        return
    if args.mode == "snapshot":
        totals = scan_registered_sources(args.source_id, process_versions=False)
        logger.info("ingestion_snapshot_complete totals=%s", totals)
        print(json.dumps(totals, sort_keys=True))
        if totals["failed_sources"]:
            raise SystemExit(1)
        return
    if args.mode == "once":
        totals = scan_registered_sources(args.source_id)
        logger.info("ingestion_scan_complete totals=%s", totals)
        if totals["failed_sources"] or totals["failed_versions"]:
            raise SystemExit(1)
        return
    while True:
        started = datetime.now(UTC)
        totals = scan_registered_sources(args.source_id)
        logger.info("ingestion_scan_complete totals=%s", totals)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        time.sleep(max(1, settings.ingest_scan_interval_seconds - elapsed))
