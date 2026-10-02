from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from pharma_intel.governance.adapter_context import AdapterContext
from pharma_intel.governance.citations import _deduplicate_prepared_facts
from pharma_intel.governance.contracts import SCHEMA_NAME, SCHEMA_VERSION, GovernanceError, PreparedSegmentFact
from pharma_intel.governance.fact_identity import _hash_json, _prepared_fact_key
from pharma_intel.governance.model_audit import _extraction_audit
from pharma_intel.governance.nextpharma import ADAPTER_NAME as NEXTPHARMA_ADAPTER_NAME
from pharma_intel.governance.nextpharma import ADAPTER_VERSION as NEXTPHARMA_ADAPTER_VERSION
from pharma_intel.governance.nextpharma import (
    NextPharmaWorkbookError,
    is_authorized_nextpharma_asset,
    parse_nextpharma_workbook,
)
from pharma_intel.governance.nextpharma import adapter_policy_manifest as nextpharma_policy_manifest
from pharma_intel.governance.policy import governance_policy_sha256
from pharma_intel.identity import IdentityError
from pharma_intel.models import (
    DataSource,
    ExtractionRun,
    RunState,
    SourceAsset,
    SourceVersion,
    StageStatus,
)


def govern_nextpharma(context: AdapterContext, version: SourceVersion) -> dict[str, int | str]:
    if not version.raw_object_uri:
        raise GovernanceError("NextPharma source version has no immutable raw workbook")
    source_context = context.session.execute(
        select(DataSource, SourceAsset)
        .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
        .where(
            DataSource.tenant_id == context.tenant_id,
            SourceAsset.tenant_id == context.tenant_id,
            SourceAsset.id == version.source_asset_id,
        )
    ).one_or_none()
    if source_context is None:
        raise GovernanceError("NextPharma source asset context is unavailable")
    source, asset = source_context
    if not is_authorized_nextpharma_asset(
        file_name=asset.file_name,
        extension=asset.extension,
        authorization_scopes=list(source.authorization_scopes or []),
    ):
        raise GovernanceError("NextPharma deterministic governance requires an authorized source asset")

    raw = context.object_store.read_bytes(
        version.raw_object_uri,
        min(source.max_file_bytes, context.settings.ingest_max_file_bytes),
    )
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if input_sha256 != version.content_sha256:
        raise GovernanceError("NextPharma immutable workbook checksum does not match its source version")
    adapter_policy = {
        "base_policy_sha256": governance_policy_sha256(context.settings),
        "source_profile": nextpharma_policy_manifest(),
    }
    policy_sha256 = _hash_json(adapter_policy)
    prompt_sha256 = _hash_json(nextpharma_policy_manifest())
    existing = context.session.scalar(
        select(ExtractionRun).where(
            ExtractionRun.tenant_id == context.tenant_id,
            ExtractionRun.source_version_id == version.id,
            ExtractionRun.schema_name == SCHEMA_NAME,
            ExtractionRun.schema_version == SCHEMA_VERSION,
            ExtractionRun.input_sha256 == input_sha256,
            ExtractionRun.policy_sha256 == policy_sha256,
        )
    )
    if existing is not None and existing.status == RunState.SUCCEEDED:
        summary = context._run_summary(existing)
        context._apply_successful_version_state(version, summary)
        context.session.commit()
        return summary
    run = existing or ExtractionRun(
        tenant_id=context.tenant_id,
        source_version_id=version.id,
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        model_provider="deterministic-adapter",
        model_name=f"{NEXTPHARMA_ADAPTER_NAME}:{NEXTPHARMA_ADAPTER_VERSION}",
        prompt_sha256=prompt_sha256,
        policy_sha256=policy_sha256,
        input_sha256=input_sha256,
    )
    if existing is None:
        context.session.add(run)
    run.model_provider = "deterministic-adapter"
    run.model_name = f"{NEXTPHARMA_ADAPTER_NAME}:{NEXTPHARMA_ADAPTER_VERSION}"
    run.prompt_sha256 = prompt_sha256
    run.policy_sha256 = policy_sha256
    run.status = RunState.RUNNING
    run.started_at = datetime.now(UTC)
    run.completed_at = None
    run.structured_output = None
    run.validation_errors = []
    run.input_tokens = None
    run.output_tokens = None
    run.estimated_cost = None
    version.governance_status = StageStatus.RUNNING
    version.error_code = None
    version.error_message = None
    context.session.commit()

    try:
        extraction = parse_nextpharma_workbook(raw)
        facts = _deduplicate_prepared_facts(
            PreparedSegmentFact(
                prepared=context.normalizer.prepare(record.fact),
                segment_index=record.row_number,
                segment_sha256=hashlib.sha256(record.source_quote.encode("utf-8")).hexdigest(),
                quote_verified=True,
                source_locator=record.source_locator,
                source_quote=record.source_quote,
            )
            for record in extraction.records
        )
    except NextPharmaWorkbookError as exc:
        error = GovernanceError(str(exc))
        context._record_failed_run(run, version, error, [], 0, 0, Decimal("0"))
        raise error from exc

    counts = {"published": 0, "review_pending": 0, "rejected": 0, "conflict": 0}
    try:
        for fact in facts:
            staged = context._stage_fact(run, version, fact, trusted_structured=True)
            counts[staged.status.value] = counts.get(staged.status.value, 0) + 1
    except (GovernanceError, IdentityError) as exc:
        policy_error = exc if isinstance(exc, GovernanceError) else GovernanceError(str(exc))
        run_id = run.id
        version_id = version.id
        context.session.rollback()
        failed_run = context.session.get(ExtractionRun, run_id)
        failed_version = context.session.get(SourceVersion, version_id)
        if failed_run is None or failed_version is None:
            raise RuntimeError("Governance failure could not recover its durable audit records") from exc
        context._record_failed_run(failed_run, failed_version, policy_error, [], 0, 0, Decimal("0"))
        if policy_error is exc:
            raise
        raise policy_error from exc

    segment_audit = {
        "segment_index": 0,
        "source_profile": NEXTPHARMA_ADAPTER_NAME,
        "input_sha256": input_sha256,
        "input_chars": None,
        "source_start_char": None,
        "source_end_char": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": "0",
        "configured_model": None,
        "response_model": run.model_name,
        "fact_keys": [_prepared_fact_key(item.prepared) for item in facts],
        "quote_verified_count": len(facts),
    }
    run.structured_output = {
        **_extraction_audit(
            [segment_audit],
            context.settings,
            Decimal("0"),
            policy_sha256=policy_sha256,
        ),
        "document_types": ["nextpharma_development_program_export"],
        "summaries": [f"Parsed {len(facts)} indication-level development program records"],
        "warnings": [],
        "fact_count": len(facts),
        "governance_schema_version": SCHEMA_VERSION,
        "normalization_versions": [],
        "deterministic_adapter": {
            "name": NEXTPHARMA_ADAPTER_NAME,
            "version": NEXTPHARMA_ADAPTER_VERSION,
            "file_name": asset.file_name,
            "query_target": extraction.query_target,
            "header_sha256": extraction.header_sha256,
            "rows_seen": extraction.rows_seen,
            "rows_emitted": len(extraction.records),
            "rows_skipped": extraction.skipped_rows,
        },
    }
    run.input_tokens = None
    run.output_tokens = None
    run.estimated_cost = 0
    run.status = RunState.SUCCEEDED
    run.completed_at = datetime.now(UTC)
    context._apply_successful_version_state(version, counts)
    context.session.commit()
    return {"run_id": run.id, "fact_count": len(facts), **counts}
