from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from pharma_intel.governance.adapter_context import AdapterContext
from pharma_intel.governance.chembl import ADAPTER_NAME as CHEMBL_ADAPTER_NAME
from pharma_intel.governance.chembl import ADAPTER_VERSION as CHEMBL_ADAPTER_VERSION
from pharma_intel.governance.chembl import adapter_policy_manifest as chembl_policy_manifest
from pharma_intel.governance.chembl import is_authorized_chembl_asset, parse_chembl_snapshot
from pharma_intel.governance.contracts import SCHEMA_NAME, SCHEMA_VERSION, GovernanceError, PreparedSegmentFact
from pharma_intel.governance.fact_identity import _hash_json, _prepared_fact_key
from pharma_intel.governance.model_audit import _extraction_audit
from pharma_intel.identity import IdentityError
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    ExtractionRun,
    RunState,
    SourceAsset,
    SourceVersion,
    StageStatus,
)


def govern_chembl(context: AdapterContext, version: SourceVersion) -> dict[str, int | str]:
    if not version.raw_object_uri:
        raise GovernanceError("ChEMBL source version has no immutable raw snapshot")
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
        raise GovernanceError("ChEMBL source asset context is unavailable")
    source, asset = source_context
    if source.source_type != DataSourceType.CHEMBL or not is_authorized_chembl_asset(
        file_name=asset.file_name,
        extension=asset.extension,
        authorization_scopes=list(source.authorization_scopes or []),
    ):
        raise GovernanceError("ChEMBL deterministic governance requires an authorized ChEMBL asset")

    raw = context.object_store.read_bytes(
        version.raw_object_uri,
        min(source.max_file_bytes, context.settings.ingest_max_file_bytes),
    )
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if input_sha256 != version.content_sha256:
        raise GovernanceError("ChEMBL immutable snapshot checksum does not match its source version")
    adapter_policy = {
        "base_policy_sha256": _hash_json(
            {
                "governance_schema": SCHEMA_VERSION,
                "source_type": DataSourceType.CHEMBL.value,
                "deterministic_policy": chembl_policy_manifest(),
            }
        ),
        "source_profile": chembl_policy_manifest(),
    }
    policy_sha256 = _hash_json(adapter_policy)
    prompt_sha256 = _hash_json(chembl_policy_manifest())
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
        model_name=f"{CHEMBL_ADAPTER_NAME}:{CHEMBL_ADAPTER_VERSION}",
        prompt_sha256=prompt_sha256,
        policy_sha256=policy_sha256,
        input_sha256=input_sha256,
    )
    if existing is None:
        context.session.add(run)
    run.model_provider = "deterministic-adapter"
    run.model_name = f"{CHEMBL_ADAPTER_NAME}:{CHEMBL_ADAPTER_VERSION}"
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
        record = parse_chembl_snapshot(raw)
        segment_sha256 = hashlib.sha256(raw).hexdigest()
        facts = [
            PreparedSegmentFact(
                prepared=context.normalizer.prepare(record.target_profile),
                segment_index=0,
                segment_sha256=segment_sha256,
                quote_verified=True,
                source_locator=record.target_profile.citation.locator,
                source_quote=record.target_profile.citation.quote,
            ),
            PreparedSegmentFact(
                prepared=context.normalizer.prepare(record.fact),
                segment_index=1,
                segment_sha256=segment_sha256,
                quote_verified=True,
                source_locator=record.source_locator,
                source_quote=record.source_quote,
            ),
        ]
    except ValueError as exc:
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

    run.structured_output = {
        **_extraction_audit(
            [
                {
                    "segment_index": 0,
                    "source_profile": CHEMBL_ADAPTER_NAME,
                    "input_sha256": input_sha256,
                    "input_chars": len(raw),
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
            ],
            context.settings,
            Decimal("0"),
            policy_sha256=policy_sha256,
        ),
        "document_types": ["chembl_target_mechanism_record"],
        "summaries": ["Parsed an authoritative ChEMBL target profile and target-mechanism record"],
        "warnings": [
            "ChEMBL maximum clinical phase is not a current-status assertion",
            "ChEMBL target identity remains separate until identity review confirms a canonical merge",
        ],
        "fact_count": len(facts),
        "governance_schema_version": SCHEMA_VERSION,
        "normalization_versions": sorted({fact.prepared.normalization_version for fact in facts}),
        "deterministic_adapter": {
            "name": CHEMBL_ADAPTER_NAME,
            "version": CHEMBL_ADAPTER_VERSION,
            "file_name": asset.file_name,
            "mechanism_id": record.mechanism_id,
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
