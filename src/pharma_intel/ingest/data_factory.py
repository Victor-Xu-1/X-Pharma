from __future__ import annotations

import hashlib
import mimetypes
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance.service import SCHEMA_NAME, SCHEMA_VERSION, GovernanceService, governance_policy_sha256
from pharma_intel.ingest.connectors import SourceConnector, SourceConnectorRegistry, SourceObject
from pharma_intel.ingest.contracts import SourceVersionReplayStage
from pharma_intel.ingest.malware import (
    MalwareDetected,
    MalwareScanner,
    MalwareScanRejected,
    MalwareScanUnavailable,
    build_malware_scanner,
)
from pharma_intel.ingest.parser_client import DocumentParser, ParserServiceUnavailable, build_document_parser
from pharma_intel.ingest.parsers import DocumentParseError
from pharma_intel.ingest.quarantine import (
    QuarantineTransitionError,
    record_clean_scan,
    record_malware_detection,
    record_rescan_failure,
)
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.scanner import sha256_file
from pharma_intel.knowledge.compiler import KnowledgeCompiler
from pharma_intel.models import (
    DataSource,
    DataSourceState,
    EvidenceClaim,
    ExtractionRun,
    IngestionFinding,
    IngestionRun,
    OutboxEvent,
    QuarantineStatus,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
)
from pharma_intel.object_store import ObjectStore, ObjectStoreError
from pharma_intel.operational_metrics import IngestionOutcome, operational_metrics

REPROCESSABLE_FAILURE_CODES = frozenset(
    {
        "malware_scan_rejected",
        "malware_scan_unavailable",
        "parser_capacity_exhausted",
        "parser_sandbox_unavailable",
        "parser_service_unavailable",
        "parse_failed",
        "snapshot_materialization_failed",
    }
)
REPROCESSABLE_GOVERNANCE_FAILURE_CODES = frozenset(
    {
        "governance_model_failed",
        "governance_budget_error",
        "governance_policy_error",
    }
)


@dataclass(frozen=True)
class ScanOutcome:
    run_id: str
    state: str
    version_ids: list[str]
    discovered: int
    unchanged: int
    unstable: int
    excluded: int
    failed: int


@dataclass(frozen=True)
class ProcessOutcome:
    version_id: str
    state: str
    malware_scan_status: str
    parse_status: str
    retrieval_status: str
    governance_status: str
    error: str | None = None


class SourceAssetReauthorizationRequired(ValueError):
    pass


class IngestionRunCanceled(RuntimeError):
    pass


class SourceVersionReplayRejected(ValueError):
    pass


def _requires_reprocessing(
    session: Session,
    version: SourceVersion,
    *,
    settings: Settings,
    include_snapshot: bool = True,
) -> bool:
    if include_snapshot and version.state == SourceVersionState.SNAPSHOTTED:
        return True
    if (
        settings.ai_governance_enabled
        and version.parse_status == StageStatus.SUCCEEDED
        and version.source_document_id is not None
        and version.extracted_text_object_uri is not None
        and version.governance_status in {StageStatus.NOT_STARTED, StageStatus.RUNNING}
        and version.state in {SourceVersionState.PARSED, SourceVersionState.GOVERNANCE_PENDING}
    ):
        active_run = session.scalar(
            select(ExtractionRun.id)
            .where(
                ExtractionRun.tenant_id == version.tenant_id,
                ExtractionRun.source_version_id == version.id,
                ExtractionRun.status.in_([RunState.PENDING, RunState.RUNNING]),
            )
            .limit(1)
        )
        if active_run is None:
            return True
    if (
        settings.ai_governance_enabled
        and version.governance_status == StageStatus.FAILED
        and version.error_code in REPROCESSABLE_GOVERNANCE_FAILURE_CODES
        and version.parse_status == StageStatus.SUCCEEDED
        and version.source_document_id is not None
        and version.extracted_text_object_uri is not None
    ):
        return True
    recoverable_failure = (
        version.state == SourceVersionState.FAILED and version.error_code in REPROCESSABLE_FAILURE_CODES
    )
    if recoverable_failure:
        return True
    if not settings.ai_governance_enabled or version.parse_status != StageStatus.SUCCEEDED:
        return False
    if version.governance_status == StageStatus.SKIPPED:
        return True
    if version.governance_status not in {StageStatus.SUCCEEDED, StageStatus.FAILED}:
        return False
    current_policy_run = session.scalar(
        select(ExtractionRun.id)
        .where(
            ExtractionRun.tenant_id == version.tenant_id,
            ExtractionRun.source_version_id == version.id,
            ExtractionRun.schema_name == SCHEMA_NAME,
            ExtractionRun.schema_version == SCHEMA_VERSION,
            ExtractionRun.policy_sha256 == governance_policy_sha256(settings),
        )
        .limit(1)
    )
    return current_policy_run is None


class DataFactoryService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        object_store: ObjectStore,
        tenant_id: str,
        heartbeat: Callable[[str], None] | None = None,
        connector_registry: SourceConnectorRegistry | None = None,
        malware_scanner: MalwareScanner | None = None,
        document_parser: DocumentParser | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.object_store = object_store
        self.tenant_id = tenant_id
        self.heartbeat = heartbeat or (lambda _: None)
        self.connector_registry = connector_registry or SourceConnectorRegistry(settings)
        self.malware_scanner = malware_scanner if malware_scanner is not None else build_malware_scanner(settings)
        self.document_parser = document_parser or build_document_parser(settings)
        set_tenant_context(session, tenant_id)

    def scan_source(
        self,
        data_source_id: str,
        workflow_id: str,
        *,
        temporal_workflow_id: str | None = None,
        temporal_run_id: str | None = None,
    ) -> ScanOutcome:
        started = time.perf_counter()
        try:
            outcome = self._scan_source(
                data_source_id,
                workflow_id,
                temporal_workflow_id=temporal_workflow_id,
                temporal_run_id=temporal_run_id,
            )
        except IngestionRunCanceled:
            self.session.rollback()
            run = self.session.scalar(
                select(IngestionRun).where(
                    IngestionRun.tenant_id == self.tenant_id,
                    IngestionRun.workflow_id == workflow_id,
                )
            )
            if run is None:
                raise
            operational_metrics().record_ingestion("scan", "skipped", time.perf_counter() - started)
            return self._outcome_from_run(run)
        except Exception as exc:
            self.session.rollback()
            run = self.session.scalar(
                select(IngestionRun).where(
                    IngestionRun.tenant_id == self.tenant_id,
                    IngestionRun.workflow_id == workflow_id,
                )
            )
            if run is not None and run.state != RunState.CANCELED:
                source = self.session.scalar(
                    select(DataSource).where(
                        DataSource.id == data_source_id,
                        DataSource.tenant_id == self.tenant_id,
                    )
                )
                now = datetime.now(UTC)
                run.state = RunState.FAILED
                run.completed_at = now
                run.heartbeat_at = now
                run.counters = {
                    "discovered": 0,
                    "unchanged": 0,
                    "unstable": 0,
                    "excluded": 0,
                    "failed": 1,
                }
                run.result = {"version_ids": []}
                run.error_summary = str(exc)[:4000]
                if source is not None:
                    source.consecutive_failures += 1
                    source.last_error = str(exc)[:4000]
                    self._finding(
                        run.id,
                        source.root_uri,
                        "scan",
                        "scan_activity_failed",
                        str(exc),
                        retryable=True,
                    )
                self.session.commit()
            operational_metrics().record_ingestion("scan", "failed", time.perf_counter() - started)
            raise
        metric_outcome: IngestionOutcome = "partial" if outcome.state == RunState.PARTIAL.value else "succeeded"
        operational_metrics().record_ingestion("scan", metric_outcome, time.perf_counter() - started)
        return outcome

    def _scan_source(
        self,
        data_source_id: str,
        workflow_id: str,
        *,
        temporal_workflow_id: str | None,
        temporal_run_id: str | None,
    ) -> ScanOutcome:
        source = self._data_source(data_source_id)
        existing_run = self.session.scalar(
            select(IngestionRun).where(
                IngestionRun.tenant_id == self.tenant_id,
                IngestionRun.workflow_id == workflow_id,
            )
        )
        if existing_run is not None and existing_run.state in {
            RunState.SUCCEEDED,
            RunState.PARTIAL,
            RunState.CANCELED,
        }:
            return self._outcome_from_run(existing_run)
        run = existing_run or IngestionRun(
            tenant_id=self.tenant_id,
            data_source_id=source.id,
            workflow_id=workflow_id,
        )
        if existing_run is None:
            self.session.add(run)
        if temporal_workflow_id is not None:
            run.temporal_workflow_id = temporal_workflow_id
        if temporal_run_id is not None:
            run.temporal_run_id = temporal_run_id
        now = datetime.now(UTC)
        run.state = RunState.RUNNING
        run.started_at = run.started_at or now
        run.heartbeat_at = now
        self.session.commit()

        if source.state in {DataSourceState.PAUSED, DataSourceState.DISABLED}:
            return self._fail_run(
                run,
                source,
                "source_not_active",
                f"Data source is {source.state.value}",
                retryable=False,
            )
        readiness = SourceReadinessService(
            self.session,
            self.settings,
            self.tenant_id,
            self.connector_registry,
        ).evaluate(source, now=now)
        if not readiness.configuration_ready:
            return self._fail_run(
                run,
                source,
                "source_governance_blocked",
                "; ".join(readiness.blocking_messages),
                retryable=False,
            )
        try:
            connector = self.connector_registry.get(source.source_type)
        except ValueError as exc:
            return self._fail_run(run, source, "unsupported_source_type", str(exc), retryable=False)

        # Persist the attempt before the connector performs network I/O. A failed
        # discovery must still respect the source cadence; otherwise an unavailable
        # provider is retried on every scheduler poll and can amplify rate limits.
        source.last_scanned_at = now
        self.session.commit()
        try:
            scan = connector.discover(source)
        except (OSError, ValueError) as exc:
            source.state = DataSourceState.UNAVAILABLE
            source.unavailable_since = source.unavailable_since or now
            source.consecutive_failures += 1
            source.last_error = str(exc)[:4000]
            for asset in self.session.scalars(
                select(SourceAsset).where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id == source.id,
                )
            ):
                asset.state = SourceAssetState.SOURCE_UNAVAILABLE
            return self._fail_run(run, source, "source_unavailable", str(exc))

        source.state = DataSourceState.ACTIVE
        source.unavailable_since = None
        source.consecutive_failures = 0
        source.last_error = None
        for asset in self.session.scalars(
            select(SourceAsset).where(
                SourceAsset.tenant_id == self.tenant_id,
                SourceAsset.data_source_id == source.id,
                SourceAsset.state == SourceAssetState.SOURCE_UNAVAILABLE,
            )
        ):
            asset.state = SourceAssetState.ACTIVE
        source.last_scanned_at = now
        seen_paths: set[str] = set()
        version_ids: list[str] = []
        unchanged = 0
        unstable = 0
        failures = 0

        for error in scan.errors:
            failures += 1
            self._finding(run.id, error.path, "discovery", "filesystem_error", error.message, retryable=True)

        for item in scan.objects:
            self._checkpoint(run.id, f"discover:{item.logical_path}")
            seen_paths.add(item.logical_path)
            if source.stable_seconds > 0 and (now - item.modified_at).total_seconds() < source.stable_seconds:
                unstable += 1
                continue
            self._ensure_run_active(run.id, "snapshot")
            try:
                version_id, changed = self._register_version(source, item, connector)
            except SourceAssetReauthorizationRequired as exc:
                failures += 1
                self._finding(
                    run.id,
                    item.source_uri,
                    "snapshot",
                    "source_asset_reauthorization_required",
                    str(exc),
                    retryable=False,
                )
                self.session.commit()
                continue
            except (OSError, ObjectStoreError, ValueError) as exc:
                failures += 1
                self._finding(run.id, item.source_uri, "snapshot", "snapshot_failed", str(exc), retryable=True)
                self.session.commit()
                continue
            if changed:
                version_ids.append(version_id)
            else:
                unchanged += 1
            run.result = {"version_ids": version_ids}
            run.counters = {
                "discovered": len(version_ids),
                "unchanged": unchanged,
                "unstable": unstable,
                "excluded": scan.excluded_count,
                "failed": failures,
            }
            run.heartbeat_at = datetime.now(UTC)
            self.session.commit()

        self._ensure_run_active(run.id, "scan_complete")
        if failures == 0 and scan.authoritative_inventory:
            assets = self.session.scalars(
                select(SourceAsset).where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id == source.id,
                )
            )
            for asset in assets:
                if asset.logical_path not in seen_paths and asset.state == SourceAssetState.ACTIVE:
                    asset.state = SourceAssetState.MISSING
                    asset.missing_since = now

        if failures == 0:
            deleted_paths = scan.deleted_paths or []
            if deleted_paths:
                deleted_assets = self.session.scalars(
                    select(SourceAsset).where(
                        SourceAsset.tenant_id == self.tenant_id,
                        SourceAsset.data_source_id == source.id,
                        SourceAsset.logical_path.in_(deleted_paths),
                    )
                )
                for asset in deleted_assets:
                    if asset.state == SourceAssetState.ACTIVE:
                        asset.state = SourceAssetState.MISSING
                        asset.missing_since = now
            queued_version_ids = set(version_ids)
            active_assets = self.session.scalars(
                select(SourceAsset).where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id == source.id,
                    SourceAsset.state == SourceAssetState.ACTIVE,
                    SourceAsset.current_version_id.is_not(None),
                )
            )
            for asset in active_assets:
                if asset.current_version_id in queued_version_ids:
                    continue
                current = self.session.get(SourceVersion, asset.current_version_id)
                if current is not None and _requires_reprocessing(
                    self.session,
                    current,
                    settings=self.settings,
                    include_snapshot=False,
                ):
                    version_ids.append(current.id)
                    queued_version_ids.add(current.id)
            source.last_success_at = now
            source.connector_cursor = scan.cursor
            source.last_cursor_at = now
        run.completed_at = datetime.now(UTC)
        run.heartbeat_at = run.completed_at
        run.state = RunState.PARTIAL if failures else RunState.SUCCEEDED
        run.counters = {
            "discovered": len(version_ids),
            "unchanged": unchanged,
            "unstable": unstable,
            "excluded": scan.excluded_count,
            "failed": failures,
        }
        run.result = {"version_ids": version_ids}
        run.error_summary = f"{failures} source items failed" if failures else None
        self.session.commit()
        return self._outcome_from_run(run)

    def _register_version(
        self,
        source: DataSource,
        item: SourceObject,
        connector: SourceConnector,
    ) -> tuple[str, bool]:
        now = datetime.now(UTC)
        asset = self.session.scalar(
            select(SourceAsset)
            .where(
                SourceAsset.tenant_id == self.tenant_id,
                SourceAsset.data_source_id == source.id,
                SourceAsset.logical_path == item.logical_path,
            )
            .with_for_update()
        )
        if asset is None:
            created_asset = True
            asset = SourceAsset(
                tenant_id=self.tenant_id,
                data_source_id=source.id,
                logical_path=item.logical_path,
                source_uri=item.source_uri,
                file_name=item.file_name,
                extension=item.extension,
                media_type=mimetypes.guess_type(item.file_name)[0],
                processing_mode=item.processing_mode,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.session.add(asset)
            self.session.flush()
        else:
            created_asset = False
            if asset.state == SourceAssetState.DELETED:
                raise SourceAssetReauthorizationRequired(
                    "Deleted source asset requires explicit operator reauthorization before it can be ingested again"
                )
            asset.source_uri = item.source_uri
            asset.last_seen_at = now
            asset.state = SourceAssetState.ACTIVE
            asset.missing_since = None

        current = self.session.get(SourceVersion, asset.current_version_id) if asset.current_version_id else None
        if (
            current is not None
            and not item.always_materialize
            and current.size_bytes == item.size_bytes
            and _same_source_timestamp(current.source_modified_at, item.modified_at)
            and (item.content_sha256 is None or current.content_sha256 == item.content_sha256)
            and (item.source_fingerprint is None or asset.source_fingerprint == item.source_fingerprint)
            and current.snapshot_status == StageStatus.SUCCEEDED
        ):
            self.session.commit()
            return current.id, _requires_reprocessing(
                self.session,
                current,
                settings=self.settings,
            )

        try:
            with connector.materialize(item) as snapshot_path:
                digest = sha256_file(snapshot_path)
                return self._persist_materialized_version(source, item, asset, snapshot_path, digest)
        except Exception:
            if created_asset:
                self.session.delete(asset)
                self.session.flush()
            raise

    def _persist_materialized_version(
        self,
        source: DataSource,
        item: SourceObject,
        asset: SourceAsset,
        snapshot_path: Path,
        digest: str,
    ) -> tuple[str, bool]:
        current = self.session.get(SourceVersion, asset.current_version_id) if asset.current_version_id else None
        if current is not None and current.content_sha256 == digest and current.raw_object_uri:
            asset.source_fingerprint = item.source_fingerprint
            self.session.commit()
            needs_processing = current.snapshot_status != StageStatus.SUCCEEDED or _requires_reprocessing(
                self.session,
                current,
                settings=self.settings,
            )
            return current.id, needs_processing

        version_number = (
            int(
                self.session.scalar(
                    select(func.coalesce(func.max(SourceVersion.version_number), 0)).where(
                        SourceVersion.tenant_id == self.tenant_id,
                        SourceVersion.source_asset_id == asset.id,
                    )
                )
                or 0
            )
            + 1
        )
        version = SourceVersion(
            tenant_id=self.tenant_id,
            source_asset_id=asset.id,
            version_number=version_number,
            content_sha256=digest,
            size_bytes=item.size_bytes,
            source_modified_at=item.modified_at,
            snapshot_status=StageStatus.RUNNING,
            metadata_json={"dataset_key": item.dataset_key, "logical_path": item.logical_path},
        )
        self.session.add(version)
        self.session.flush()
        asset.current_version_id = version.id
        try:
            stored = self.object_store.put_file(self.tenant_id, "raw", snapshot_path, digest)
        except Exception as exc:
            version.snapshot_status = StageStatus.FAILED
            version.state = SourceVersionState.FAILED
            version.error_code = "snapshot_failed"
            version.error_message = str(exc)[:4000]
            self.session.commit()
            raise
        version.raw_object_uri = stored.uri
        version.snapshot_status = StageStatus.SUCCEEDED
        version.state = SourceVersionState.SNAPSHOTTED
        asset.source_fingerprint = item.source_fingerprint
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="source_version",
                aggregate_id=version.id,
                event_type="source.version.snapshotted",
                payload={"source_version_id": version.id, "content_sha256": digest},
            )
        )
        self.session.commit()
        return version.id, True

    def process_version(
        self,
        source_version_id: str,
        ingestion_run_id: str | None = None,
        from_stage: SourceVersionReplayStage = "malware_scan",
    ) -> ProcessOutcome:
        started = time.perf_counter()
        try:
            outcome = self._process_version(source_version_id, ingestion_run_id, from_stage)
        except ParserServiceUnavailable:
            operational_metrics().record_ingestion("process", "retry", time.perf_counter() - started)
            raise
        except Exception:
            operational_metrics().record_ingestion("process", "failed", time.perf_counter() - started)
            raise
        if outcome.error:
            metric_outcome: IngestionOutcome = "failed"
        elif outcome.state == SourceVersionState.ASSET_ONLY.value:
            metric_outcome = "skipped"
        else:
            metric_outcome = "succeeded"
        operational_metrics().record_ingestion("process", metric_outcome, time.perf_counter() - started)
        return outcome

    def _process_version(
        self,
        source_version_id: str,
        ingestion_run_id: str | None,
        from_stage: SourceVersionReplayStage,
    ) -> ProcessOutcome:
        self._checkpoint(ingestion_run_id, "version_start")
        version = self.session.scalar(
            select(SourceVersion).where(
                SourceVersion.id == source_version_id,
                SourceVersion.tenant_id == self.tenant_id,
            )
        )
        if version is None:
            raise LookupError("Source version not found")
        asset = self.session.scalar(
            select(SourceAsset).where(
                SourceAsset.id == version.source_asset_id,
                SourceAsset.tenant_id == self.tenant_id,
            )
        )
        if asset is None:
            raise LookupError("Source asset not found")
        if from_stage == "auto":
            from_stage = self._automatic_replay_stage(version)
        self._validate_processing_stage(version, from_stage)
        if from_stage == "retrieval":
            return self._queue_retrieval_projection(version, ingestion_run_id)
        if from_stage == "governance":
            version.error_code = None
            version.error_message = None
            version.governance_status = StageStatus.NOT_STARTED
            version.retrieval_status = StageStatus.NOT_STARTED
            version.state = SourceVersionState.GOVERNANCE_PENDING
            self.session.commit()
            return self._govern_and_project(version, ingestion_run_id)
        if version.snapshot_status != StageStatus.SUCCEEDED or not version.raw_object_uri:
            return self._version_failure(version, "snapshot_missing", "Immutable source snapshot is not available")
        version.error_code = None
        version.error_message = None
        if from_stage == "malware_scan":
            version.malware_scan_status = (
                StageStatus.RUNNING if self.malware_scanner is not None else StageStatus.SKIPPED
            )
        version.parse_status = StageStatus.NOT_STARTED
        version.retrieval_status = StageStatus.NOT_STARTED
        version.governance_status = StageStatus.NOT_STARTED
        version.state = SourceVersionState.SNAPSHOTTED
        self.session.commit()

        with tempfile.TemporaryDirectory(prefix="pharma-ingest-") as temporary:
            self._checkpoint(ingestion_run_id, "materialize")
            local_path = Path(temporary) / asset.file_name
            try:
                self.object_store.materialize(version.raw_object_uri, local_path)
                if sha256_file(local_path) != version.content_sha256:
                    raise ObjectStoreError("Materialized object failed checksum verification")
            except (ObjectStoreError, OSError, ValueError) as exc:
                return self._malware_failure(version, "snapshot_materialization_failed", str(exc))

            if from_stage == "malware_scan":
                if self.malware_scanner is None:
                    if version.quarantine_status not in {
                        QuarantineStatus.NOT_APPLICABLE,
                        QuarantineStatus.CLEARED,
                    }:
                        return self._malware_failure(
                            version,
                            "malware_scan_unavailable",
                            "Quarantined content requires an enabled malware scanner",
                        )
                    version.malware_scan_status = StageStatus.SKIPPED
                    version.malware_scanner = None
                    version.malware_signature_version = None
                    version.malware_scanned_at = datetime.now(UTC)
                    metadata = dict(version.metadata_json)
                    metadata["malware_scan"] = {
                        "status": "skipped",
                        "reason": "Malware scanning is disabled for this environment",
                    }
                    version.metadata_json = metadata
                    self.session.commit()
                else:
                    self._checkpoint(ingestion_run_id, "malware_scan")
                    try:
                        scan_result = self.malware_scanner.scan(local_path)
                    except MalwareDetected as exc:
                        threat_name = "".join(
                            character if character.isprintable() else "?" for character in exc.threat_name
                        )
                        return self._malware_failure(
                            version,
                            "malware_detected",
                            "Malicious content was detected",
                            threat_name=threat_name[:240],
                        )
                    except MalwareScanRejected as exc:
                        return self._malware_failure(version, "malware_scan_rejected", str(exc))
                    except MalwareScanUnavailable as exc:
                        return self._malware_failure(version, "malware_scan_unavailable", str(exc))
                    version.malware_scan_status = StageStatus.SUCCEEDED
                    version.malware_scanner = scan_result.scanner
                    version.malware_signature_version = scan_result.signature_version[:240]
                    version.malware_scanned_at = datetime.now(UTC)
                    metadata = dict(version.metadata_json)
                    metadata["malware_scan"] = {
                        "status": "clean",
                        "scanner": scan_result.scanner,
                        "signature_version": scan_result.signature_version[:240],
                    }
                    version.metadata_json = metadata
                    try:
                        record_clean_scan(
                            self.session,
                            version,
                            scanner=scan_result.scanner,
                            signature_version=scan_result.signature_version,
                        )
                    except QuarantineTransitionError as exc:
                        raise SourceVersionReplayRejected(str(exc)) from exc
                    self.session.commit()

            if asset.processing_mode == "asset":
                source_document = self._source_document(version, asset)
                version.source_document_id = source_document.id
                version.parse_status = StageStatus.SKIPPED
                version.retrieval_status = StageStatus.SKIPPED
                version.governance_status = StageStatus.SKIPPED
                version.state = SourceVersionState.ASSET_ONLY
                self.session.commit()
                return self._process_outcome(version)

            version.parse_status = StageStatus.RUNNING
            self.session.commit()
            self._checkpoint(ingestion_run_id, "parse")
            try:
                parsed = self.document_parser.parse(local_path, self.settings.parser_max_text_chars)
                text_bytes = parsed.text.encode("utf-8")
                text_sha256 = hashlib.sha256(text_bytes).hexdigest()
                text_object = self.object_store.put_bytes(
                    self.tenant_id,
                    "extracted-text",
                    text_bytes,
                    text_sha256,
                    ".txt",
                )
                source_document = self._source_document(version, asset, parsed.metadata)
                version.source_document_id = source_document.id
                version.extracted_text_object_uri = text_object.uri
                version.extracted_text_sha256 = text_sha256
                version.parser_name = parsed.parser_name
                version.parser_version = parsed.parser_version
                version.parse_status = StageStatus.SUCCEEDED
                version.state = SourceVersionState.PARSED
                self.session.commit()
                version.retrieval_status = StageStatus.NOT_STARTED
                metadata = dict(version.metadata_json)
                metadata["retrieval_projection"] = {
                    "engine": "opensearch",
                    "status": "queued",
                    "reason": "Awaiting transactional outbox projection",
                }
                version.metadata_json = metadata
                self.session.commit()
            except ParserServiceUnavailable as exc:
                self._version_retry_wait(version, exc.error_code or "parser_service_unavailable", str(exc))
                raise
            except (DocumentParseError, ObjectStoreError, OSError, ValueError) as exc:
                return self._version_failure(version, "parse_failed", str(exc))

        return self._govern_and_project(version, ingestion_run_id)

    @staticmethod
    def _automatic_replay_stage(version: SourceVersion) -> SourceVersionReplayStage:
        if (
            version.parse_status == StageStatus.SUCCEEDED
            and version.source_document_id is not None
            and version.extracted_text_object_uri is not None
            and version.governance_status
            in {
                StageStatus.NOT_STARTED,
                StageStatus.RUNNING,
                StageStatus.FAILED,
            }
            and version.state
            in {
                SourceVersionState.PARSED,
                SourceVersionState.GOVERNANCE_PENDING,
            }
        ):
            return "governance"
        if (
            version.parse_status == StageStatus.SUCCEEDED
            and version.source_document_id is not None
            and version.governance_status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
            and version.retrieval_status != StageStatus.SUCCEEDED
        ):
            return "retrieval"
        return "malware_scan"

    def _govern_and_project(
        self,
        version: SourceVersion,
        ingestion_run_id: str | None,
    ) -> ProcessOutcome:
        self._checkpoint(ingestion_run_id, "governance")
        if self.settings.ai_governance_enabled:
            version.governance_status = StageStatus.NOT_STARTED
            version.state = SourceVersionState.GOVERNANCE_PENDING
            self.session.commit()
            GovernanceService(
                self.session,
                self.settings,
                self.object_store,
                self.tenant_id,
            ).govern_version(version.id)
            self.session.refresh(version)
            self._compile_knowledge_for_version(version.id)
        else:
            version.governance_status = StageStatus.SKIPPED
            metadata = dict(version.metadata_json)
            metadata["governance"] = {"status": "skipped", "reason": "AI governance is disabled"}
            version.metadata_json = metadata
        return self._queue_retrieval_projection(version, ingestion_run_id)

    def _queue_retrieval_projection(
        self,
        version: SourceVersion,
        ingestion_run_id: str | None,
    ) -> ProcessOutcome:
        if version.source_document_id is None:
            raise SourceVersionReplayRejected("Retrieval replay requires a parsed source document")
        self._checkpoint(ingestion_run_id, "projection")
        version.error_code = None
        version.error_message = None
        version.retrieval_status = StageStatus.NOT_STARTED
        metadata = dict(version.metadata_json)
        metadata["retrieval_projection"] = {
            "engine": "opensearch",
            "status": "queued",
            "reason": "Awaiting transactional outbox projection",
        }
        version.metadata_json = metadata
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="source_version",
                aggregate_id=version.id,
                event_type="source.version.parsed",
                payload={"source_version_id": version.id, "source_document_id": version.source_document_id},
            )
        )
        self.session.commit()
        return self._process_outcome(version)

    def _validate_processing_stage(
        self,
        version: SourceVersion,
        from_stage: SourceVersionReplayStage,
    ) -> None:
        if from_stage not in {"malware_scan", "parse", "governance", "retrieval"}:
            raise SourceVersionReplayRejected(f"Unsupported source-version replay stage: {from_stage}")
        if from_stage == "malware_scan":
            if version.quarantine_status in {
                QuarantineStatus.PENDING_REVIEW,
                QuarantineStatus.HELD,
                QuarantineStatus.REJECTED,
            }:
                raise SourceVersionReplayRejected("Quarantined content requires an explicit operator rescan decision")
            return
        if version.quarantine_status not in {
            QuarantineStatus.NOT_APPLICABLE,
            QuarantineStatus.CLEARED,
        }:
            raise SourceVersionReplayRejected("Quarantined content cannot bypass malware scanning")
        if version.snapshot_status != StageStatus.SUCCEEDED or not version.raw_object_uri:
            raise SourceVersionReplayRejected("Replay requires an immutable source snapshot")
        if from_stage == "parse":
            if version.malware_scan_status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                raise SourceVersionReplayRejected("Parse replay requires a completed malware scan")
            return
        if version.parse_status != StageStatus.SUCCEEDED or version.source_document_id is None:
            raise SourceVersionReplayRejected(f"{from_stage} replay requires a parsed source document")
        if from_stage == "governance":
            if not self.settings.ai_governance_enabled:
                raise SourceVersionReplayRejected("AI governance is disabled")
            if not version.extracted_text_object_uri:
                raise SourceVersionReplayRejected("Governance replay requires extracted text")

    def _checkpoint(self, ingestion_run_id: str | None, stage: str) -> None:
        self.heartbeat(stage)
        if ingestion_run_id is not None:
            self._ensure_run_active(ingestion_run_id, stage)

    def _ensure_run_active(self, ingestion_run_id: str, stage: str) -> None:
        run = self.session.scalar(
            select(IngestionRun).where(
                IngestionRun.id == ingestion_run_id,
                IngestionRun.tenant_id == self.tenant_id,
            )
        )
        if run is None:
            raise LookupError("Ingestion run not found")
        self.session.refresh(run, attribute_names=["state", "cancel_requested_at"])
        if run.state == RunState.CANCELED or run.cancel_requested_at is not None:
            raise IngestionRunCanceled(f"Ingestion run was canceled before stage {stage}")

    def _compile_knowledge_for_version(self, source_version_id: str) -> None:
        claim_ids = list(
            self.session.scalars(
                select(StagedFact.published_resource_id)
                .join(ExtractionRun, ExtractionRun.id == StagedFact.extraction_run_id)
                .where(
                    StagedFact.tenant_id == self.tenant_id,
                    ExtractionRun.source_version_id == source_version_id,
                    StagedFact.published_resource_type == "evidence_claim",
                    StagedFact.published_resource_id.is_not(None),
                )
            )
        )
        if not claim_ids:
            return
        subject_ids = set(
            self.session.scalars(
                select(EvidenceClaim.subject_id).where(
                    EvidenceClaim.tenant_id == self.tenant_id,
                    EvidenceClaim.id.in_(claim_ids),
                )
            )
        )
        compiler = KnowledgeCompiler(self.session, self.tenant_id)
        for subject_id in sorted(subject_ids):
            result = compiler.compile_entity(subject_id, run_id=f"source-version:{source_version_id}")
            compiler.export_page(result.page_id, self.settings.markdown_export_root)

    def _source_document(
        self,
        version: SourceVersion,
        asset: SourceAsset,
        parser_metadata: dict[str, Any] | None = None,
    ) -> SourceDocument:
        document = self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.tenant_id == self.tenant_id,
                SourceDocument.content_sha256 == version.content_sha256,
            )
        )
        location = {"source_uri": asset.source_uri, "logical_path": asset.logical_path}
        if document is None:
            document = SourceDocument(
                tenant_id=self.tenant_id,
                title=asset.file_name,
                source_type=self._data_source(asset.data_source_id).source_type.value,
                source_uri=asset.source_uri,
                canonical_uri=version.raw_object_uri,
                content_sha256=version.content_sha256,
                published_at=version.source_modified_at,
                metadata_json={"source_locations": [location], "parser": parser_metadata or {}},
            )
            self.session.add(document)
            self.session.flush()
            return document
        metadata = dict(document.metadata_json)
        locations = list(metadata.get("source_locations") or [])
        if location not in locations:
            locations.append(location)
        metadata["source_locations"] = locations
        if parser_metadata:
            metadata["parser"] = parser_metadata
        document.metadata_json = metadata
        return document

    def _data_source(self, data_source_id: str) -> DataSource:
        source = self.session.scalar(
            select(DataSource).where(
                DataSource.id == data_source_id,
                DataSource.tenant_id == self.tenant_id,
            )
        )
        if source is None:
            raise LookupError("Data source not found")
        return source

    def _finding(
        self,
        run_id: str,
        source_path: str,
        stage: str,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        self.session.add(
            IngestionFinding(
                tenant_id=self.tenant_id,
                ingestion_run_id=run_id,
                source_path=source_path,
                stage=stage,
                code=code,
                message=message[:4000],
                retryable=retryable,
            )
        )

    def _fail_run(
        self,
        run: IngestionRun,
        source: DataSource,
        code: str,
        message: str,
        *,
        retryable: bool = True,
    ) -> ScanOutcome:
        now = datetime.now(UTC)
        run.state = RunState.FAILED
        run.completed_at = now
        run.heartbeat_at = now
        run.counters = {"discovered": 0, "unchanged": 0, "unstable": 0, "excluded": 0, "failed": 1}
        run.result = {"version_ids": []}
        run.error_summary = message[:4000]
        source.last_scanned_at = now
        source.last_error = message[:4000]
        self._finding(run.id, source.root_uri, "discovery", code, message, retryable=retryable)
        self.session.commit()
        return self._outcome_from_run(run)

    def _version_failure(self, version: SourceVersion, code: str, message: str) -> ProcessOutcome:
        version.parse_status = StageStatus.FAILED
        version.state = SourceVersionState.FAILED
        version.error_code = code
        version.error_message = message[:4000]
        self.session.commit()
        return self._process_outcome(version, message)

    def _version_retry_wait(self, version: SourceVersion, code: str, message: str) -> None:
        version.parse_status = StageStatus.NOT_STARTED
        version.state = SourceVersionState.SNAPSHOTTED
        version.error_code = code
        version.error_message = message[:4000]
        self.session.commit()

    def _malware_failure(
        self,
        version: SourceVersion,
        code: str,
        message: str,
        *,
        threat_name: str | None = None,
    ) -> ProcessOutcome:
        version.malware_scan_status = StageStatus.FAILED
        version.malware_scanned_at = datetime.now(UTC)
        version.state = SourceVersionState.FAILED
        version.error_code = code
        version.error_message = message[:4000]
        metadata = dict(version.metadata_json)
        malware_metadata = {"status": "failed", "reason_code": code}
        if threat_name:
            malware_metadata["threat_name"] = threat_name
        metadata["malware_scan"] = malware_metadata
        version.metadata_json = metadata
        try:
            if code == "malware_detected":
                record_malware_detection(self.session, version, threat_name=threat_name)
            else:
                record_rescan_failure(
                    self.session,
                    version,
                    reason=f"Malware rescan failed: {code}",
                    actor_id="data-factory",
                )
        except QuarantineTransitionError as exc:
            raise SourceVersionReplayRejected(str(exc)) from exc
        self.session.commit()
        return self._process_outcome(version, message)

    @staticmethod
    def _outcome_from_run(run: IngestionRun) -> ScanOutcome:
        counters = run.counters
        version_ids = run.result.get("version_ids") or []
        return ScanOutcome(
            run_id=run.id,
            state=run.state.value,
            version_ids=[str(value) for value in version_ids],
            discovered=int(counters.get("discovered", 0)),
            unchanged=int(counters.get("unchanged", 0)),
            unstable=int(counters.get("unstable", 0)),
            excluded=int(counters.get("excluded", 0)),
            failed=int(counters.get("failed", 0)),
        )

    @staticmethod
    def _process_outcome(version: SourceVersion, error: str | None = None) -> ProcessOutcome:
        return ProcessOutcome(
            version_id=version.id,
            state=version.state.value,
            malware_scan_status=version.malware_scan_status.value,
            parse_status=version.parse_status.value,
            retrieval_status=version.retrieval_status.value,
            governance_status=version.governance_status.value,
            error=error,
        )


def _same_source_timestamp(stored: datetime | None, discovered: datetime) -> bool:
    if stored is None:
        return False
    normalized_stored = stored.replace(tzinfo=UTC) if stored.tzinfo is None else stored.astimezone(UTC)
    normalized_discovered = discovered.replace(tzinfo=UTC) if discovered.tzinfo is None else discovered.astimezone(UTC)
    return normalized_stored == normalized_discovered


def outcome_dict(outcome: ScanOutcome | ProcessOutcome) -> dict[str, Any]:
    return asdict(outcome)
