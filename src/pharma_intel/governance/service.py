from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pharma_intel.chemistry.types import ChemistryValidationError
from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.enterprise.llm_providers import effective_ai_settings
from pharma_intel.governance.chembl import (
    ADAPTER_NAME as CHEMBL_ADAPTER_NAME,
)
from pharma_intel.governance.chembl import (
    ADAPTER_VERSION as CHEMBL_ADAPTER_VERSION,
)
from pharma_intel.governance.chembl import (
    adapter_policy_manifest as chembl_policy_manifest,
)
from pharma_intel.governance.chembl import (
    is_authorized_chembl_asset,
    parse_chembl_snapshot,
)
from pharma_intel.governance.clinicaltrials_gov import (
    ADAPTER_NAME as CLINICALTRIALS_GOV_ADAPTER_NAME,
)
from pharma_intel.governance.clinicaltrials_gov import (
    ADAPTER_VERSION as CLINICALTRIALS_GOV_ADAPTER_VERSION,
)
from pharma_intel.governance.clinicaltrials_gov import (
    adapter_policy_manifest as clinicaltrials_gov_policy_manifest,
)
from pharma_intel.governance.clinicaltrials_gov import (
    is_authorized_clinicaltrials_gov_asset,
    parse_clinicaltrials_gov_snapshot,
)
from pharma_intel.governance.model_gateway import (
    ModelGatewayError,
    OpenAICompatibleExtractionGateway,
    extraction_schema,
    extraction_system_prompt,
)
from pharma_intel.governance.nextpharma import (
    ADAPTER_NAME as NEXTPHARMA_ADAPTER_NAME,
)
from pharma_intel.governance.nextpharma import (
    ADAPTER_VERSION as NEXTPHARMA_ADAPTER_VERSION,
)
from pharma_intel.governance.nextpharma import (
    NextPharmaWorkbookError,
    is_authorized_nextpharma_asset,
    parse_nextpharma_workbook,
)
from pharma_intel.governance.nextpharma import (
    adapter_policy_manifest as nextpharma_policy_manifest,
)
from pharma_intel.governance.normalization import FactNormalizer, PreparedFact
from pharma_intel.governance.schemas import (
    ActivityFact,
    ClaimFact,
    DealFact,
    EpidemiologyFact,
    ExtractedFact,
    ExtractionEnvelope,
    NewsFact,
    PatentFact,
    ProgramFact,
    RegulatoryFact,
    StructureFact,
    TargetEvidenceFact,
    TargetProfileFact,
    TrialFact,
)
from pharma_intel.identity import EntityIdentityService, IdentityError, normalize_name
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    CompoundStructure,
    DataSource,
    DataSourceType,
    DealAssetAssociation,
    DealDirection,
    DealPartyAssociation,
    DealPartyRole,
    DealProfile,
    DealRight,
    DealStatus,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    EpidemiologyObservation,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    MeasurementRelation,
    NewsEvent,
    OutboxEvent,
    PatentFamily,
    PatientPopulation,
    PatientPopulationEntityLink,
    ProgramTargetRole,
    RegulatoryEvent,
    Relationship,
    ReviewStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
    TargetEvidenceObservation,
    TargetProfile,
    TrialEntityRole,
)
from pharma_intel.object_store import ObjectStore

SCHEMA_NAME = "pharma_document_facts"
SCHEMA_VERSION = "2.13.0"
POLICY_SCHEMA = "pharma.governance-policy.v1"
HIGH_RISK_FACT_KINDS = frozenset(
    {
        "activity",
        "deal",
        "epidemiology",
        "news",
        "patent",
        "program",
        "regulatory",
        "structure",
        "target_evidence",
        "trial",
    }
)
MILLION_TOKENS = Decimal("1000000")
CLINICALTRIALS_PROFILE_INPUT_STRING_CHARS = 1200


class GovernanceError(RuntimeError):
    pass


class GovernanceBudgetError(GovernanceError):
    pass


def recover_stale_extraction_runs(
    session: Session,
    settings: Settings,
    tenant_id: str,
    *,
    now: datetime | None = None,
) -> int:
    """Close abandoned model runs without changing already successful versions."""
    set_tenant_context(session, tenant_id)
    recovered_at = now or datetime.now(UTC)
    stale_before = recovered_at - timedelta(seconds=settings.ai_stale_run_seconds)
    runs = list(
        session.scalars(
            select(ExtractionRun)
            .where(
                ExtractionRun.tenant_id == tenant_id,
                ExtractionRun.status == RunState.RUNNING,
                ExtractionRun.started_at.is_not(None),
                ExtractionRun.started_at < stale_before,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for run in runs:
        version = session.scalar(
            select(SourceVersion).where(
                SourceVersion.id == run.source_version_id,
                SourceVersion.tenant_id == tenant_id,
            )
        )
        run.status = RunState.FAILED
        run.completed_at = recovered_at
        validation_errors = list(run.validation_errors or [])
        validation_errors.append(
            {
                "code": "stale_run_recovered",
                "message": "Model governance run exceeded the stale-run recovery window",
                "recovered_at": recovered_at.isoformat(),
            }
        )
        run.validation_errors = validation_errors[-20:]
        if version is not None and version.governance_status == StageStatus.RUNNING:
            version.governance_status = StageStatus.NOT_STARTED
            version.retrieval_status = StageStatus.NOT_STARTED
            version.state = (
                SourceVersionState.PARSED
                if version.parse_status == StageStatus.SUCCEEDED
                else SourceVersionState.SNAPSHOTTED
            )
            version.error_code = "stale_governance_run_recovered"
            version.error_message = "Previous governance run exceeded the recovery window"
    if runs:
        session.commit()
    return len(runs)


@dataclass(frozen=True)
class DocumentSegment:
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class SourceQuoteMatch:
    locator: str
    quote: str


@dataclass(frozen=True)
class PreparedSegmentFact:
    prepared: PreparedFact
    segment_index: int
    segment_sha256: str
    quote_verified: bool
    source_locator: str | None
    source_quote: str | None


class GovernanceService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        object_store: ObjectStore,
        tenant_id: str,
        gateway: OpenAICompatibleExtractionGateway | None = None,
        normalizer: FactNormalizer | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.object_store = object_store
        self.tenant_id = tenant_id
        self.gateway = gateway
        self.normalizer = normalizer or FactNormalizer()
        self._trusted_identity_mode_cache: dict[str, bool] = {}
        self._source_type_cache: dict[str, DataSourceType | None] = {}
        set_tenant_context(session, tenant_id)

    def govern_version(self, source_version_id: str) -> dict[str, int | str]:
        version = self.session.scalar(
            select(SourceVersion).where(
                SourceVersion.id == source_version_id,
                SourceVersion.tenant_id == self.tenant_id,
            )
        )
        if version is None:
            raise LookupError("Source version not found")
        if version.parse_status != StageStatus.SUCCEEDED or not version.extracted_text_object_uri:
            raise GovernanceError("Source version has not completed deterministic text extraction")
        source_profile = self._source_profile(version)
        if source_profile == NEXTPHARMA_ADAPTER_NAME:
            return self._govern_nextpharma(version)
        if source_profile == CHEMBL_ADAPTER_NAME:
            return self._govern_chembl(version)
        if source_profile == CLINICALTRIALS_GOV_ADAPTER_NAME:
            return self._govern_clinicaltrials_gov(version)
        ai_settings = effective_ai_settings(self.session, self.settings, self.tenant_id)
        data = self.object_store.read_bytes(
            version.extracted_text_object_uri,
            self.settings.parser_max_text_chars * 4,
        )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GovernanceError("Extracted text object is not valid UTF-8") from exc
        profile_input_limit = (
            min(self.settings.ai_max_model_string_chars, CLINICALTRIALS_PROFILE_INPUT_STRING_CHARS)
            if source_profile == "clinicaltrials_gov"
            else self.settings.ai_max_model_string_chars
        )
        model_text, profile_identity = _profiled_model_text(
            text,
            source_profile,
            max_string_chars=profile_input_limit,
        )
        if source_profile == "clinicaltrials_gov":
            fact_kind_allowlist = frozenset({"trial"})
            max_facts = 1
        elif source_profile == "pubmed":
            fact_kind_allowlist = frozenset({"claim"})
            max_facts = min(5, self.settings.ai_max_facts_per_segment)
        else:
            fact_kind_allowlist = None
            max_facts = self.settings.ai_max_facts_per_segment
        input_sha256 = hashlib.sha256(data).hexdigest()
        prompt_sha256 = hashlib.sha256(
            extraction_system_prompt(
                max_facts,
                self.settings.ai_max_model_string_chars,
                fact_kind_allowlist=fact_kind_allowlist,
                source_profile=source_profile,
            ).encode()
        ).hexdigest()
        policy_sha256 = governance_policy_sha256(ai_settings)
        existing = self.session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.tenant_id == self.tenant_id,
                ExtractionRun.source_version_id == version.id,
                ExtractionRun.schema_name == SCHEMA_NAME,
                ExtractionRun.schema_version == SCHEMA_VERSION,
                ExtractionRun.input_sha256 == input_sha256,
                ExtractionRun.policy_sha256 == policy_sha256,
            )
        )
        if existing is not None and existing.status == RunState.SUCCEEDED:
            summary = self._run_summary(existing)
            self._apply_successful_version_state(version, summary)
            self.session.commit()
            return summary
        run = existing or ExtractionRun(
            tenant_id=self.tenant_id,
            source_version_id=version.id,
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            model_provider="openai-compatible",
            model_name=ai_settings.ai_model,
            prompt_sha256=prompt_sha256,
            policy_sha256=policy_sha256,
            input_sha256=input_sha256,
        )
        if existing is None:
            self.session.add(run)
        run.model_name = ai_settings.ai_model
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
        self.session.commit()

        envelopes: list[ExtractionEnvelope] = []
        prepared_segment_facts: list[PreparedSegmentFact] = []
        segment_audits: list[dict[str, Any]] = []
        input_tokens = 0
        output_tokens = 0
        estimated_cost = Decimal("0")
        try:
            if not model_text.strip():
                raise GovernanceError("Extracted text is empty")
            if len(model_text) > self.settings.ai_max_document_chars:
                raise GovernanceBudgetError("Extracted text exceeds the configured AI document character budget")
            if source_profile is not None and len(model_text) > self.settings.ai_max_input_chars:
                raise GovernanceBudgetError("Profiled source exceeds the configured AI segment budget")
            segments = _segments(model_text, self.settings.ai_max_input_chars)
            if len(segments) > self.settings.ai_max_segments_per_document:
                raise GovernanceBudgetError("Extracted text exceeds the configured AI segment budget")
            gateway = self.gateway or OpenAICompatibleExtractionGateway(ai_settings)
            for segment_index, segment in enumerate(segments):
                if source_profile is None:
                    response = gateway.extract(segment.text)
                else:
                    response = gateway.extract(
                        segment.text,
                        fact_kind_allowlist=fact_kind_allowlist,
                        max_facts=max_facts,
                        source_profile=source_profile,
                    )
                envelope = _enforce_profiled_identity(response.envelope, source_profile, profile_identity)
                _validate_profiled_response(envelope, source_profile, profile_identity)
                envelopes.append(envelope)
                response_input_tokens = response.input_tokens or 0
                response_output_tokens = response.output_tokens or 0
                input_tokens += response_input_tokens
                output_tokens += response_output_tokens
                estimated_cost += _model_cost(
                    response_input_tokens,
                    response_output_tokens,
                    self.settings.ai_input_cost_per_million_tokens,
                    self.settings.ai_output_cost_per_million_tokens,
                )
                if input_tokens > self.settings.ai_max_document_input_tokens:
                    raise GovernanceBudgetError("AI input token usage exceeded the configured document budget")
                if output_tokens > self.settings.ai_max_document_output_tokens:
                    raise GovernanceBudgetError("AI output token usage exceeded the configured document budget")
                if self.settings.ai_max_document_cost > 0 and estimated_cost > self.settings.ai_max_document_cost:
                    raise GovernanceBudgetError("AI token cost exceeded the configured document budget")
                segment_sha256 = hashlib.sha256(segment.text.encode("utf-8")).hexdigest()
                segment_facts: list[PreparedSegmentFact] = []
                for prepared in (self.normalizer.prepare(fact) for fact in envelope.facts):
                    source_segment = (
                        segment
                        if source_profile is None
                        else DocumentSegment(text=text, start_char=0, end_char=len(text))
                    )
                    source_match = _quote_source_match(
                        prepared.fact.citation.quote,
                        source_segment,
                    )
                    segment_facts.append(
                        PreparedSegmentFact(
                            prepared=prepared,
                            segment_index=segment_index,
                            segment_sha256=segment_sha256,
                            quote_verified=source_match is not None,
                            source_locator=source_match.locator if source_match is not None else None,
                            source_quote=source_match.quote if source_match is not None else None,
                        )
                    )
                prepared_segment_facts.extend(segment_facts)
                segment_audits.append(
                    {
                        "segment_index": segment_index,
                        "source_profile": source_profile,
                        "input_sha256": segment_sha256,
                        "input_chars": len(segment.text),
                        "source_start_char": segment.start_char,
                        "source_end_char": segment.end_char,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "estimated_cost": format(
                            _model_cost(
                                response_input_tokens,
                                response_output_tokens,
                                self.settings.ai_input_cost_per_million_tokens,
                                self.settings.ai_output_cost_per_million_tokens,
                            ),
                            "f",
                        ),
                        "configured_model": self.settings.ai_model,
                        "response_model": response.model_name,
                        "system_fingerprint": response.system_fingerprint,
                        "provider_request_id": response.provider_request_id,
                        "client_request_id": response.client_request_id,
                        "prompt_variant": response.prompt_variant,
                        "finish_reason": response.finish_reason,
                        "response_sha256": response.response_sha256,
                        "fact_keys": [_prepared_fact_key(item.prepared) for item in segment_facts],
                        "quote_verified_count": sum(item.quote_verified for item in segment_facts),
                    }
                )
        except (ModelGatewayError, GovernanceError) as exc:
            self._record_failed_run(
                run,
                version,
                exc,
                segment_audits,
                input_tokens,
                output_tokens,
                estimated_cost,
            )
            raise

        facts = _deduplicate_prepared_facts(prepared_segment_facts)
        counts = {"published": 0, "review_pending": 0, "rejected": 0, "conflict": 0}
        try:
            for fact in facts:
                staged = self._stage_fact(run, version, fact)
                counts[staged.status.value] = counts.get(staged.status.value, 0) + 1
        except (GovernanceError, IdentityError) as exc:
            policy_error = exc if isinstance(exc, GovernanceError) else GovernanceError(str(exc))
            run_id = run.id
            version_id = version.id
            self.session.rollback()
            failed_run = self.session.get(ExtractionRun, run_id)
            failed_version = self.session.get(SourceVersion, version_id)
            if failed_run is None or failed_version is None:
                raise RuntimeError("Governance failure could not recover its durable audit records") from exc
            self._record_failed_run(
                failed_run,
                failed_version,
                policy_error,
                segment_audits,
                input_tokens,
                output_tokens,
                estimated_cost,
            )
            if policy_error is exc:
                raise
            raise policy_error from exc

        run.structured_output = {
            **_extraction_audit(segment_audits, self.settings, estimated_cost),
            "document_types": sorted({envelope.document_type for envelope in envelopes}),
            "summaries": [envelope.document_summary for envelope in envelopes],
            "warnings": [warning for envelope in envelopes for warning in envelope.warnings],
            "fact_count": len(facts),
            "governance_schema_version": SCHEMA_VERSION,
            "normalization_versions": sorted(
                {
                    fact.prepared.normalization_version
                    for fact in facts
                    if fact.prepared.normalization_version is not None
                }
            ),
        }
        run.input_tokens = input_tokens or None
        run.output_tokens = output_tokens or None
        run.estimated_cost = float(estimated_cost)
        run.status = RunState.SUCCEEDED
        run.completed_at = datetime.now(UTC)
        self._apply_successful_version_state(version, counts)
        self.session.commit()
        return {"run_id": run.id, "fact_count": len(facts), **counts}

    def _govern_clinicaltrials_gov(self, version: SourceVersion) -> dict[str, int | str]:
        if not version.raw_object_uri:
            raise GovernanceError("ClinicalTrials.gov source version has no immutable raw snapshot")
        source_context = self.session.execute(
            select(DataSource, SourceAsset)
            .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
            .where(
                DataSource.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
                SourceAsset.id == version.source_asset_id,
            )
        ).one_or_none()
        if source_context is None:
            raise GovernanceError("ClinicalTrials.gov source asset context is unavailable")
        source, asset = source_context
        if source.source_type != DataSourceType.CLINICALTRIALS_GOV or not is_authorized_clinicaltrials_gov_asset(
            root_uri=source.root_uri,
            logical_path=asset.logical_path,
            source_uri=asset.source_uri,
            file_name=asset.file_name,
            extension=asset.extension,
            authorization_scopes=list(source.authorization_scopes or []),
        ):
            raise GovernanceError(
                "ClinicalTrials.gov deterministic governance requires an authorized official API snapshot"
            )

        raw = self.object_store.read_bytes(
            version.raw_object_uri,
            min(source.max_file_bytes, self.settings.ingest_max_file_bytes),
        )
        input_sha256 = hashlib.sha256(raw).hexdigest()
        if input_sha256 != version.content_sha256:
            raise GovernanceError("ClinicalTrials.gov immutable snapshot checksum does not match its source version")
        policy_manifest = clinicaltrials_gov_policy_manifest()
        policy_sha256 = _hash_json(policy_manifest)
        prompt_sha256 = _hash_json(policy_manifest)
        existing = self.session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.tenant_id == self.tenant_id,
                ExtractionRun.source_version_id == version.id,
                ExtractionRun.schema_name == SCHEMA_NAME,
                ExtractionRun.schema_version == SCHEMA_VERSION,
                ExtractionRun.input_sha256 == input_sha256,
                ExtractionRun.policy_sha256 == policy_sha256,
            )
        )
        if existing is not None and existing.status == RunState.SUCCEEDED:
            summary = self._run_summary(existing)
            self._apply_successful_version_state(version, summary)
            self.session.commit()
            return summary
        run = existing or ExtractionRun(
            tenant_id=self.tenant_id,
            source_version_id=version.id,
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            model_provider="deterministic-adapter",
            model_name=f"{CLINICALTRIALS_GOV_ADAPTER_NAME}:{CLINICALTRIALS_GOV_ADAPTER_VERSION}",
            prompt_sha256=prompt_sha256,
            policy_sha256=policy_sha256,
            input_sha256=input_sha256,
        )
        if existing is None:
            self.session.add(run)
        run.model_provider = "deterministic-adapter"
        run.model_name = f"{CLINICALTRIALS_GOV_ADAPTER_NAME}:{CLINICALTRIALS_GOV_ADAPTER_VERSION}"
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
        self.session.commit()

        try:
            record = parse_clinicaltrials_gov_snapshot(raw)
            segment_fact = PreparedSegmentFact(
                prepared=self.normalizer.prepare(record.fact),
                segment_index=0,
                segment_sha256=input_sha256,
                quote_verified=True,
                source_locator=record.source_locator,
                source_quote=record.source_quote,
            )
        except ValueError as exc:
            error = GovernanceError(str(exc))
            self._record_failed_run(run, version, error, [], 0, 0, Decimal("0"))
            raise error from exc

        counts = {"published": 0, "review_pending": 0, "rejected": 0, "conflict": 0}
        try:
            staged = self._stage_fact(run, version, segment_fact, trusted_structured=True)
            counts[staged.status.value] = counts.get(staged.status.value, 0) + 1
        except (GovernanceError, IdentityError) as exc:
            policy_error = exc if isinstance(exc, GovernanceError) else GovernanceError(str(exc))
            run_id = run.id
            version_id = version.id
            self.session.rollback()
            failed_run = self.session.get(ExtractionRun, run_id)
            failed_version = self.session.get(SourceVersion, version_id)
            if failed_run is None or failed_version is None:
                raise RuntimeError("Governance failure could not recover its durable audit records") from exc
            self._record_failed_run(failed_run, failed_version, policy_error, [], 0, 0, Decimal("0"))
            if policy_error is exc:
                raise
            raise policy_error from exc

        run.structured_output = {
            **_extraction_audit(
                [
                    {
                        "segment_index": 0,
                        "source_profile": CLINICALTRIALS_GOV_ADAPTER_NAME,
                        "input_sha256": input_sha256,
                        "input_chars": len(raw),
                        "source_start_char": None,
                        "source_end_char": None,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "estimated_cost": "0",
                        "configured_model": None,
                        "response_model": run.model_name,
                        "fact_keys": [_prepared_fact_key(segment_fact.prepared)],
                        "quote_verified_count": 1,
                    }
                ],
                self.settings,
                Decimal("0"),
                policy_sha256=policy_sha256,
            ),
            "document_types": ["clinicaltrials_gov_api_v2_study"],
            "summaries": [f"Parsed authoritative registry record {record.fact.registry_id}"],
            "warnings": [
                "Drug identity links are created only for unique exact matches to verified entities",
                "Target attribution and qualitative efficacy conclusions are not inferred from registry text",
            ],
            "fact_count": 1,
            "governance_schema_version": SCHEMA_VERSION,
            "normalization_versions": [],
            "deterministic_adapter": {
                "name": CLINICALTRIALS_GOV_ADAPTER_NAME,
                "version": CLINICALTRIALS_GOV_ADAPTER_VERSION,
                "file_name": asset.file_name,
                "registry_id": record.fact.registry_id,
            },
        }
        run.input_tokens = None
        run.output_tokens = None
        run.estimated_cost = 0
        run.status = RunState.SUCCEEDED
        run.completed_at = datetime.now(UTC)
        self._apply_successful_version_state(version, counts)
        self.session.commit()
        return {"run_id": run.id, "fact_count": 1, **counts}

    def _govern_nextpharma(self, version: SourceVersion) -> dict[str, int | str]:
        if not version.raw_object_uri:
            raise GovernanceError("NextPharma source version has no immutable raw workbook")
        source_context = self.session.execute(
            select(DataSource, SourceAsset)
            .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
            .where(
                DataSource.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
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

        raw = self.object_store.read_bytes(
            version.raw_object_uri,
            min(source.max_file_bytes, self.settings.ingest_max_file_bytes),
        )
        input_sha256 = hashlib.sha256(raw).hexdigest()
        if input_sha256 != version.content_sha256:
            raise GovernanceError("NextPharma immutable workbook checksum does not match its source version")
        adapter_policy = {
            "base_policy_sha256": governance_policy_sha256(self.settings),
            "source_profile": nextpharma_policy_manifest(),
        }
        policy_sha256 = _hash_json(adapter_policy)
        prompt_sha256 = _hash_json(nextpharma_policy_manifest())
        existing = self.session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.tenant_id == self.tenant_id,
                ExtractionRun.source_version_id == version.id,
                ExtractionRun.schema_name == SCHEMA_NAME,
                ExtractionRun.schema_version == SCHEMA_VERSION,
                ExtractionRun.input_sha256 == input_sha256,
                ExtractionRun.policy_sha256 == policy_sha256,
            )
        )
        if existing is not None and existing.status == RunState.SUCCEEDED:
            summary = self._run_summary(existing)
            self._apply_successful_version_state(version, summary)
            self.session.commit()
            return summary
        run = existing or ExtractionRun(
            tenant_id=self.tenant_id,
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
            self.session.add(run)
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
        self.session.commit()

        try:
            extraction = parse_nextpharma_workbook(raw)
            facts = _deduplicate_prepared_facts(
                PreparedSegmentFact(
                    prepared=self.normalizer.prepare(record.fact),
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
            self._record_failed_run(run, version, error, [], 0, 0, Decimal("0"))
            raise error from exc

        counts = {"published": 0, "review_pending": 0, "rejected": 0, "conflict": 0}
        try:
            for fact in facts:
                staged = self._stage_fact(run, version, fact, trusted_structured=True)
                counts[staged.status.value] = counts.get(staged.status.value, 0) + 1
        except (GovernanceError, IdentityError) as exc:
            policy_error = exc if isinstance(exc, GovernanceError) else GovernanceError(str(exc))
            run_id = run.id
            version_id = version.id
            self.session.rollback()
            failed_run = self.session.get(ExtractionRun, run_id)
            failed_version = self.session.get(SourceVersion, version_id)
            if failed_run is None or failed_version is None:
                raise RuntimeError("Governance failure could not recover its durable audit records") from exc
            self._record_failed_run(failed_run, failed_version, policy_error, [], 0, 0, Decimal("0"))
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
                self.settings,
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
        self._apply_successful_version_state(version, counts)
        self.session.commit()
        return {"run_id": run.id, "fact_count": len(facts), **counts}

    def _govern_chembl(self, version: SourceVersion) -> dict[str, int | str]:
        if not version.raw_object_uri:
            raise GovernanceError("ChEMBL source version has no immutable raw snapshot")
        source_context = self.session.execute(
            select(DataSource, SourceAsset)
            .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
            .where(
                DataSource.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
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

        raw = self.object_store.read_bytes(
            version.raw_object_uri,
            min(source.max_file_bytes, self.settings.ingest_max_file_bytes),
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
        existing = self.session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.tenant_id == self.tenant_id,
                ExtractionRun.source_version_id == version.id,
                ExtractionRun.schema_name == SCHEMA_NAME,
                ExtractionRun.schema_version == SCHEMA_VERSION,
                ExtractionRun.input_sha256 == input_sha256,
                ExtractionRun.policy_sha256 == policy_sha256,
            )
        )
        if existing is not None and existing.status == RunState.SUCCEEDED:
            summary = self._run_summary(existing)
            self._apply_successful_version_state(version, summary)
            self.session.commit()
            return summary
        run = existing or ExtractionRun(
            tenant_id=self.tenant_id,
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
            self.session.add(run)
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
        self.session.commit()

        try:
            record = parse_chembl_snapshot(raw)
            segment_sha256 = hashlib.sha256(raw).hexdigest()
            facts = [
                PreparedSegmentFact(
                    prepared=self.normalizer.prepare(record.target_profile),
                    segment_index=0,
                    segment_sha256=segment_sha256,
                    quote_verified=True,
                    source_locator=record.target_profile.citation.locator,
                    source_quote=record.target_profile.citation.quote,
                ),
                PreparedSegmentFact(
                    prepared=self.normalizer.prepare(record.fact),
                    segment_index=1,
                    segment_sha256=segment_sha256,
                    quote_verified=True,
                    source_locator=record.source_locator,
                    source_quote=record.source_quote,
                ),
            ]
        except ValueError as exc:
            error = GovernanceError(str(exc))
            self._record_failed_run(run, version, error, [], 0, 0, Decimal("0"))
            raise error from exc

        counts = {"published": 0, "review_pending": 0, "rejected": 0, "conflict": 0}
        try:
            for fact in facts:
                staged = self._stage_fact(run, version, fact, trusted_structured=True)
                counts[staged.status.value] = counts.get(staged.status.value, 0) + 1
        except (GovernanceError, IdentityError) as exc:
            policy_error = exc if isinstance(exc, GovernanceError) else GovernanceError(str(exc))
            run_id = run.id
            version_id = version.id
            self.session.rollback()
            failed_run = self.session.get(ExtractionRun, run_id)
            failed_version = self.session.get(SourceVersion, version_id)
            if failed_run is None or failed_version is None:
                raise RuntimeError("Governance failure could not recover its durable audit records") from exc
            self._record_failed_run(failed_run, failed_version, policy_error, [], 0, 0, Decimal("0"))
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
                self.settings,
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
        self._apply_successful_version_state(version, counts)
        self.session.commit()
        return {"run_id": run.id, "fact_count": len(facts), **counts}

    def _source_profile(self, version: SourceVersion) -> str | None:
        source_context = self.session.execute(
            select(DataSource, SourceAsset)
            .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
            .where(
                DataSource.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
                SourceAsset.id == version.source_asset_id,
            )
        ).one_or_none()
        if source_context is None:
            return None
        source, asset = source_context
        source_type = source.source_type
        if source_type == DataSourceType.CLINICALTRIALS_GOV:
            return CLINICALTRIALS_GOV_ADAPTER_NAME
        if source_type == DataSourceType.PUBMED:
            return "pubmed"
        if source_type == DataSourceType.CHEMBL:
            return CHEMBL_ADAPTER_NAME
        if is_authorized_nextpharma_asset(
            file_name=asset.file_name,
            extension=asset.extension,
            authorization_scopes=list(source.authorization_scopes or []),
        ):
            return NEXTPHARMA_ADAPTER_NAME
        return None

    @staticmethod
    def _apply_successful_version_state(
        version: SourceVersion,
        counts: Mapping[str, int | str],
    ) -> None:
        version.governance_status = StageStatus.SUCCEEDED
        version.error_code = None
        version.error_message = None
        if int(counts.get("review_pending", 0)) or int(counts.get("conflict", 0)):
            version.state = SourceVersionState.REVIEW_PENDING
        elif int(counts.get("published", 0)):
            version.state = SourceVersionState.PUBLISHED
        elif version.retrieval_status == StageStatus.SUCCEEDED:
            version.state = SourceVersionState.INDEXED
        else:
            version.state = SourceVersionState.PARSED

    def _record_failed_run(
        self,
        run: ExtractionRun,
        version: SourceVersion,
        exc: ModelGatewayError | GovernanceError,
        segment_audits: list[dict[str, Any]],
        input_tokens: int,
        output_tokens: int,
        estimated_cost: Decimal,
    ) -> None:
        if isinstance(exc, ModelGatewayError):
            error_code = "model_gateway_error"
            version_error_code = "governance_model_failed"
        elif isinstance(exc, GovernanceBudgetError):
            error_code = "governance_budget_error"
            version_error_code = error_code
        else:
            error_code = "governance_policy_error"
            version_error_code = error_code
        run.status = RunState.FAILED
        run.completed_at = datetime.now(UTC)
        run.validation_errors = [{"code": error_code, "message": str(exc)[:4000]}]
        run.input_tokens = input_tokens or None
        run.output_tokens = output_tokens or None
        run.estimated_cost = float(estimated_cost)
        run.structured_output = _extraction_audit(segment_audits, self.settings, estimated_cost)
        version.governance_status = StageStatus.FAILED
        version.error_code = version_error_code
        version.error_message = str(exc)[:4000]
        self.session.commit()

    def _stage_fact(
        self,
        run: ExtractionRun,
        version: SourceVersion,
        segment_fact: PreparedSegmentFact,
        *,
        trusted_structured: bool = False,
    ) -> StagedFact:
        prepared = segment_fact.prepared
        fact = prepared.fact
        payload = prepared.payload
        fact_key = _prepared_fact_key(prepared)
        existing = self.session.scalar(
            select(StagedFact).where(
                StagedFact.tenant_id == self.tenant_id,
                StagedFact.extraction_run_id == run.id,
                StagedFact.fact_key == fact_key,
            )
        )
        if existing is not None:
            return existing
        quality_findings = list(prepared.quality_findings)
        if not segment_fact.quote_verified:
            quality_findings.append(
                {
                    "code": "quote_not_found_in_segment",
                    "severity": "error",
                    "message": "Citation quote is absent from the exact model input segment",
                    "segment_index": segment_fact.segment_index,
                    "segment_sha256": segment_fact.segment_sha256,
                }
            )
        prior = list(
            self.session.scalars(
                select(StagedFact).where(
                    StagedFact.tenant_id == self.tenant_id,
                    StagedFact.fact_key == fact_key,
                    StagedFact.status.in_(
                        [
                            GovernanceStatus.APPROVED,
                            GovernanceStatus.PUBLISHED,
                            GovernanceStatus.REVIEW_PENDING,
                            GovernanceStatus.CONFLICT,
                        ]
                    ),
                )
            )
        )
        authoritative_trial = (
            trusted_structured
            and isinstance(fact, TrialFact)
            and fact.citation.confidence == 1
            and self._source_type_for_document(version.source_document_id) == DataSourceType.CLINICALTRIALS_GOV
        )
        superseded_prior = (
            [item for item in prior if item.status in {GovernanceStatus.REVIEW_PENDING, GovernanceStatus.CONFLICT}]
            if authoritative_trial
            else []
        )
        superseded_ids = {item.id for item in superseded_prior}
        conflicts = [
            item.id
            for item in prior
            if item.id not in superseded_ids
            and _payload_without_citation(item.payload) != _payload_without_citation(payload)
        ]
        if conflicts:
            quality_findings.append(
                {"code": "conflicting_fact", "severity": "warning", "message": "A prior fact has different values"}
            )

        canonical_conflict = self._structure_entity_conflict(prepared, quality_findings)

        if prepared.hard_reject or not segment_fact.quote_verified:
            status = GovernanceStatus.REJECTED
        elif prepared.normalization_conflict or canonical_conflict or conflicts:
            status = GovernanceStatus.CONFLICT
        elif (
            trusted_structured and isinstance(fact, ProgramFact | TargetProfileFact) and fact.citation.confidence == 1
        ) or authoritative_trial:
            status = GovernanceStatus.VALIDATED
        elif (
            fact.fact_kind in HIGH_RISK_FACT_KINDS
            or fact.fact_kind not in self.settings.ai_auto_publish_fact_kinds
            or fact.citation.confidence < self.settings.ai_auto_publish_threshold
        ):
            status = GovernanceStatus.REVIEW_PENDING
        else:
            status = GovernanceStatus.VALIDATED
        staged = StagedFact(
            tenant_id=self.tenant_id,
            extraction_run_id=run.id,
            fact_kind=fact.fact_kind,
            fact_key=fact_key,
            raw_payload=prepared.raw_payload,
            payload=payload,
            normalization_version=prepared.normalization_version,
            source_document_id=version.source_document_id,
            source_locator=segment_fact.source_locator,
            source_quote=segment_fact.source_quote or fact.citation.quote,
            confidence=fact.citation.confidence,
            status=status,
            quality_findings=quality_findings,
            conflict_with_ids=conflicts,
        )
        self.session.add(staged)
        self.session.flush()
        if superseded_prior:
            self._withdraw_superseded_facts(superseded_prior)
        if status == GovernanceStatus.VALIDATED:
            self._publish(staged)
        elif status in {GovernanceStatus.REVIEW_PENDING, GovernanceStatus.CONFLICT}:
            self.session.add(
                ReviewTask(
                    tenant_id=self.tenant_id,
                    staged_fact_id=staged.id,
                    status=GovernanceStatus.REVIEW_PENDING,
                    priority=90 if status == GovernanceStatus.CONFLICT else 50,
                    reasons=quality_findings
                    or [{"code": "policy_review", "message": "Fact type or confidence requires human review"}],
                )
            )
        return staged

    def _withdraw_superseded_facts(self, facts: list[StagedFact]) -> None:
        decided_at = datetime.now(UTC)
        for fact in facts:
            fact.status = GovernanceStatus.WITHDRAWN
            task = self.session.scalar(
                select(ReviewTask).where(
                    ReviewTask.tenant_id == self.tenant_id,
                    ReviewTask.staged_fact_id == fact.id,
                    ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
                )
            )
            if task is None:
                continue
            task.status = GovernanceStatus.WITHDRAWN
            task.decision_notes = "Superseded by an authoritative ClinicalTrials.gov deterministic snapshot"
            task.decided_at = decided_at

    def _structure_entity_conflict(
        self,
        prepared: PreparedFact,
        quality_findings: list[dict[str, Any]],
    ) -> bool:
        if not isinstance(prepared.fact, StructureFact) or prepared.hard_reject:
            return False
        inchi_key = prepared.payload.get("standard_inchi_key")
        if not isinstance(inchi_key, str):
            return False
        structure = self.session.scalar(
            select(CompoundStructure).where(
                CompoundStructure.tenant_id == self.tenant_id,
                CompoundStructure.standard_inchi_key == inchi_key,
            )
        )
        if structure is None:
            return False
        entity = self.session.scalar(
            select(Entity).where(
                Entity.id == structure.entity_id,
                Entity.tenant_id == self.tenant_id,
            )
        )
        if entity is not None and _reference_matches_entity(prepared.payload["subject"], entity):
            return False
        quality_findings.append(
            {
                "code": "structure_entity_conflict",
                "severity": "error",
                "message": "RDKit-derived InChIKey is already assigned to another normalized entity",
                "existing_structure_id": structure.id,
                "existing_entity_id": structure.entity_id,
                "existing_entity_name": entity.name if entity is not None else None,
            }
        )
        return True

    def approve_fact(self, staged_fact_id: str, user_id: str, notes: str | None = None) -> StagedFact:
        staged, task = self._reviewable(staged_fact_id)
        if staged.status == GovernanceStatus.CONFLICT and not (notes or "").strip():
            raise GovernanceError("Conflict approval requires reviewer decision notes")
        try:
            with self.session.begin_nested():
                self._publish(staged)
                task.status = GovernanceStatus.APPROVED
                task.decided_by_user_id = user_id
                task.decision_notes = notes
                task.decided_at = datetime.now(UTC)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return staged

    def reject_fact(self, staged_fact_id: str, user_id: str, notes: str) -> StagedFact:
        staged, task = self._reviewable(staged_fact_id)
        staged.status = GovernanceStatus.REJECTED
        task.status = GovernanceStatus.REJECTED
        task.decided_by_user_id = user_id
        task.decision_notes = notes
        task.decided_at = datetime.now(UTC)
        self.session.commit()
        return staged

    def _reviewable(self, staged_fact_id: str) -> tuple[StagedFact, ReviewTask]:
        staged = self.session.scalar(
            select(StagedFact).where(
                StagedFact.id == staged_fact_id,
                StagedFact.tenant_id == self.tenant_id,
                StagedFact.status.in_([GovernanceStatus.REVIEW_PENDING, GovernanceStatus.CONFLICT]),
            )
        )
        if staged is None:
            raise LookupError("Reviewable staged fact not found")
        task = self.session.scalar(
            select(ReviewTask).where(
                ReviewTask.tenant_id == self.tenant_id,
                ReviewTask.staged_fact_id == staged.id,
                ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
            )
        )
        if task is None:
            raise LookupError("Open review task not found")
        return staged, task

    def _publish(self, staged: StagedFact) -> None:
        if staged.source_document_id is None:
            raise GovernanceError("A fact cannot be published without a source document")
        payload = staged.payload
        subject_ref = _primary_subject(payload)
        subject = self._entity(subject_ref, staged.source_document_id)
        object_entity = None
        if staged.fact_kind == "claim" and isinstance(payload.get("object_entity"), dict):
            object_entity = self._entity(cast(dict[str, Any], payload["object_entity"]), staged.source_document_id)
        predicate = str(payload.get("predicate") or f"has_{staged.fact_kind}")
        claim = self.session.scalar(
            select(EvidenceClaim).where(
                EvidenceClaim.tenant_id == self.tenant_id,
                EvidenceClaim.subject_id == subject.id,
                EvidenceClaim.predicate == predicate,
                EvidenceClaim.source_document_id == staged.source_document_id,
                EvidenceClaim.source_locator == staged.source_locator,
            )
        )
        if claim is None:
            claim = EvidenceClaim(
                tenant_id=self.tenant_id,
                subject_id=subject.id,
                predicate=predicate,
                object_id=object_entity.id if object_entity else None,
                value=None if object_entity else payload,
                source_document_id=staged.source_document_id,
                source_locator=staged.source_locator,
                quote=staged.source_quote,
                confidence=staged.confidence,
                review_status=ReviewStatus.VERIFIED,
            )
            self.session.add(claim)
            self.session.flush()
        projections = self._materialize_structured_fact(staged, payload)
        self._link_provenance(staged, claim, projections)
        staged.status = GovernanceStatus.PUBLISHED
        staged.published_resource_type = "evidence_claim"
        staged.published_resource_id = claim.id
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="evidence_claim",
                aggregate_id=claim.id,
                event_type="governance.fact.published",
                payload={
                    "evidence_claim_id": claim.id,
                    "staged_fact_id": staged.id,
                    "structured_projections": projections,
                },
            )
        )

    def _link_provenance(
        self,
        staged: StagedFact,
        claim: EvidenceClaim,
        projections: list[dict[str, str]],
    ) -> None:
        source = self.session.execute(
            select(SourceVersion, SourceAsset, DataSource)
            .join(ExtractionRun, ExtractionRun.source_version_id == SourceVersion.id)
            .join(SourceAsset, SourceAsset.id == SourceVersion.source_asset_id)
            .join(DataSource, DataSource.id == SourceAsset.data_source_id)
            .where(
                ExtractionRun.id == staged.extraction_run_id,
                ExtractionRun.tenant_id == self.tenant_id,
                SourceVersion.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
                DataSource.tenant_id == self.tenant_id,
            )
        ).one_or_none()
        if source is None:
            raise GovernanceError("A published fact must retain its source version and dataset")
        version, asset, data_source = source
        if version.source_document_id != staged.source_document_id:
            raise GovernanceError("Published fact source document does not match its source version")
        resources = [("evidence_claim", claim.id)] + [
            (projection["resource_type"], projection["resource_id"]) for projection in projections
        ]
        existing = set(
            self.session.execute(
                select(FactProvenanceLink.resource_type, FactProvenanceLink.resource_id).where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.staged_fact_id == staged.id,
                )
            ).all()
        )
        for resource_type, resource_id in resources:
            if (resource_type, resource_id) in existing:
                continue
            self.session.add(
                FactProvenanceLink(
                    tenant_id=self.tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    staged_fact_id=staged.id,
                    evidence_claim_id=claim.id,
                    source_asset_id=asset.id,
                    source_version_id=version.id,
                    source_document_id=staged.source_document_id,
                    dataset_key=data_source.dataset_key,
                    source_locator=staged.source_locator,
                )
            )

    def _materialize_structured_fact(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        fact_kind = staged.fact_kind
        if fact_kind == "claim":
            return []
        if fact_kind == "target_profile":
            subject = self._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
            profile = self.session.scalar(
                select(TargetProfile).where(
                    TargetProfile.tenant_id == self.tenant_id,
                    TargetProfile.entity_id == subject.id,
                )
            )
            if profile is None:
                profile = TargetProfile(
                    tenant_id=self.tenant_id,
                    entity_id=subject.id,
                    organism=str(payload.get("organism") or "Homo sapiens"),
                )
                self.session.add(profile)
            for field in ("gene_symbol", "uniprot_accession", "target_class", "function_summary"):
                if payload.get(field) is not None:
                    setattr(profile, field, payload[field])
            if payload.get("sequence") is not None:
                profile.sequence = re.sub(r"\s+", "", str(payload["sequence"])).upper()
            if payload.get("organism") is not None:
                profile.organism = str(payload["organism"])
            profile.source_document_id = staged.source_document_id
            self.session.flush()
            return [_projection("target_profile", profile.id)]
        if fact_kind == "target_evidence":
            return self._materialize_target_evidence(staged, payload)
        if fact_kind == "structure":
            return self._materialize_structure(staged, payload)
        if fact_kind == "activity":
            return self._materialize_activity(staged, payload)
        if fact_kind == "program":
            return self._materialize_program(staged, payload)
        if fact_kind == "trial":
            return self._materialize_trial(staged, payload)
        if fact_kind == "patent":
            return self._materialize_patent(staged, payload)
        if fact_kind == "deal":
            return self._materialize_deal(staged, payload)
        if fact_kind == "regulatory":
            return self._materialize_regulatory(staged, payload)
        if fact_kind == "epidemiology":
            return self._materialize_epidemiology(staged, payload)
        if fact_kind == "news":
            return self._materialize_news(staged, payload)
        raise GovernanceError(f"Unsupported structured fact kind: {fact_kind}")

    def _materialize_target_evidence(
        self,
        staged: StagedFact,
        payload: dict[str, Any],
    ) -> list[dict[str, str]]:
        target = self._entity(cast(dict[str, Any], payload["target"]), staged.source_document_id)
        disease = self._optional_entity(payload.get("disease"), staged.source_document_id)
        observation = self.session.scalar(
            select(TargetEvidenceObservation).where(
                TargetEvidenceObservation.tenant_id == self.tenant_id,
                TargetEvidenceObservation.source_system == "governed_ai",
                TargetEvidenceObservation.source_record_id == payload["record_identifier"],
            )
        )
        if observation is None:
            observation = TargetEvidenceObservation(
                tenant_id=self.tenant_id,
                source_system="governed_ai",
                source_record_id=str(payload["record_identifier"]),
                target_entity_id=target.id,
                disease_entity_id=disease.id if disease else None,
                evidence_type=str(payload["evidence_type"]),
                direction=str(payload["direction"]),
                summary=str(payload["summary"]),
            )
            self.session.add(observation)
        elif observation.target_entity_id != target.id:
            raise GovernanceError("Target evidence record identifier is already assigned to another target")
        incoming_observed_at = _optional_datetime(payload.get("observed_at"))
        if _should_update_temporal_state(observation.observed_at, incoming_observed_at):
            observation.disease_entity_id = disease.id if disease else None
            observation.evidence_type = str(payload["evidence_type"])
            observation.direction = str(payload["direction"])
            observation.study_name = cast(str | None, payload.get("study_name"))
            observation.population = cast(str | None, payload.get("population"))
            observation.tissue = cast(str | None, payload.get("tissue"))
            observation.variant = cast(str | None, payload.get("variant"))
            observation.effect_size = cast(float | None, payload.get("effect_size"))
            observation.effect_unit = cast(str | None, payload.get("effect_unit"))
            observation.p_value = cast(float | None, payload.get("p_value"))
            observation.sample_size = cast(int | None, payload.get("sample_size"))
            observation.summary = str(payload["summary"])
            observation.observed_at = incoming_observed_at
            observation.qualifiers = dict(payload.get("qualifiers") or {})
            observation.source_document_id = staged.source_document_id
        if disease:
            self._relationship(target, "associated_with_disease", disease, staged)
        self.session.flush()
        return [_projection("target_evidence", observation.id)]

    def _materialize_structure(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        try:
            standardized = self.normalizer.verify_structure_payload(payload)
        except ChemistryValidationError as exc:
            raise GovernanceError(f"Structure payload failed authority verification: {exc}") from exc
        if staged.normalization_version != standardized.standardization_version:
            raise GovernanceError("Staged structure normalization version does not match its governed payload")

        entity = self._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
        inchi_key = standardized.standard_inchi_key
        structure = self.session.scalar(
            select(CompoundStructure).where(
                CompoundStructure.tenant_id == self.tenant_id,
                CompoundStructure.standard_inchi_key == inchi_key,
            )
        )
        if structure is None:
            structure = CompoundStructure(
                tenant_id=self.tenant_id,
                entity_id=entity.id,
                canonical_smiles=standardized.canonical_smiles,
                isomeric_smiles=standardized.isomeric_smiles,
                standard_inchi=standardized.standard_inchi,
                standard_inchi_key=inchi_key,
                molecular_formula=standardized.molecular_formula,
                molecular_weight=standardized.molecular_weight,
                exact_mass=standardized.exact_mass,
                structure_version=f"ai-governed/{SCHEMA_VERSION}",
                standardization_version=standardized.standardization_version,
            )
            self.session.add(structure)
        elif structure.entity_id != entity.id:
            raise GovernanceError("InChIKey is already assigned to another normalized entity")
        else:
            authoritative_fields: dict[str, str | float] = {
                "canonical_smiles": standardized.canonical_smiles,
                "isomeric_smiles": standardized.isomeric_smiles,
                "standard_inchi": standardized.standard_inchi,
                "molecular_formula": standardized.molecular_formula,
                "molecular_weight": standardized.molecular_weight,
                "exact_mass": standardized.exact_mass,
            }
            for field, expected in authoritative_fields.items():
                current = getattr(structure, field)
                if current is not None and not _authority_value_matches(current, expected):
                    raise GovernanceError(f"Existing structure field {field} conflicts with the RDKit authority")
                if current is None:
                    setattr(structure, field, expected)
            structure.standardization_version = standardized.standardization_version
        self.session.flush()
        return [_projection("compound_structure", structure.id)]

    def _materialize_activity(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        compound = self._entity(cast(dict[str, Any], payload["compound"]), staged.source_document_id)
        target = self._entity(cast(dict[str, Any], payload["target"]), staged.source_document_id)
        assay_identity = hashlib.sha256(
            f"{staged.source_document_id}:{str(payload['assay_name']).casefold()}".encode()
        ).hexdigest()
        assay = self.session.scalar(
            select(Assay).where(
                Assay.tenant_id == self.tenant_id,
                Assay.source_system == "governed_ai",
                Assay.source_assay_id == assay_identity,
            )
        )
        if assay is None:
            assay = Assay(
                tenant_id=self.tenant_id,
                source_system="governed_ai",
                source_assay_id=assay_identity,
                target_entity_id=target.id,
                assay_type=cast(str | None, payload.get("assay_type")),
                description=str(payload["assay_name"]),
                source_document_id=staged.source_document_id,
            )
            self.session.add(assay)
            self.session.flush()
        activity = self.session.scalar(
            select(ActivityMeasurement).where(
                ActivityMeasurement.tenant_id == self.tenant_id,
                ActivityMeasurement.source_system == "governed_ai",
                ActivityMeasurement.source_activity_id == staged.fact_key,
            )
        )
        relation = MeasurementRelation(str(payload["reported_relation"]))
        if activity is None:
            activity = ActivityMeasurement(
                tenant_id=self.tenant_id,
                source_system="governed_ai",
                source_activity_id=staged.fact_key,
                assay_id=assay.id,
                compound_entity_id=compound.id,
                target_entity_id=target.id,
                reported_type=str(payload["reported_type"]),
                reported_relation=relation,
                reported_value=str(payload["reported_value"]),
            )
            self.session.add(activity)
        activity.reported_units = cast(str | None, payload.get("reported_units"))
        activity.standard_type = str(payload["reported_type"]) if payload.get("standard_value") is not None else None
        activity.standard_relation = relation if payload.get("standard_value") is not None else None
        activity.standard_value = cast(float | None, payload.get("standard_value"))
        activity.standard_units = cast(str | None, payload.get("standard_units"))
        activity.qualifiers = {"staged_fact_id": staged.id, "evidence_claim_pending": True}
        self._relationship(compound, "has_target", target, staged)
        self.session.flush()
        return [_projection("assay", assay.id), _projection("activity_measurement", activity.id)]

    def _materialize_program(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        drug = self._entity(cast(dict[str, Any], payload["drug"]), staged.source_document_id)
        target_facts = list(payload.get("targets") or [])
        if payload.get("target") is not None:
            target_facts = [{"role": ProgramTargetRole.PRIMARY.value, "entity": payload["target"]}]
        targets = [
            (
                ProgramTargetRole(str(item["role"])),
                self._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id),
            )
            for item in target_facts
        ]
        targets.sort(key=lambda item: (item[0] != ProgramTargetRole.PRIMARY, item[1].id))
        disease = self._optional_entity(payload.get("indication"), staged.source_document_id)
        organization = self._optional_entity(payload.get("organization"), staged.source_document_id)
        organization_facts = list(payload.get("organizations") or [])
        if organization is not None and not any(item.get("role") == "originator" for item in organization_facts):
            # A legacy organization is authoritative for the originator identity. Keep it
            # when newer payloads also carry collaborators instead of silently dropping it.
            organization_facts.append({"role": "originator", "entity": payload["organization"]})
        organizations = [
            (
                str(item["role"]),
                self._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id),
                cast(str | None, item.get("country_region")),
                cast(str | None, item.get("organization_type")),
            )
            for item in organization_facts
        ]
        organizations.sort(key=lambda item: (item[0] != "originator", item[1].id))
        if organization is None:
            organization = next((entity for role, entity, _, _ in organizations if role == "originator"), None)
        phase = _normalize_phase(str(payload["phase"]))
        if phase is None:
            self._defer_projection(
                staged,
                "unsupported_development_phase",
                f"Program phase {payload['phase']!r} is not in the controlled phase vocabulary.",
            )
            return []
        regional_phases: dict[str, DevelopmentPhase | None] = {}
        for field_name in ("global_phase", "china_phase"):
            raw_phase = payload.get(field_name)
            normalized = _normalize_phase(str(raw_phase)) if raw_phase is not None else None
            if raw_phase is not None and normalized is None:
                self._defer_projection(
                    staged,
                    f"unsupported_{field_name}",
                    f"Program {field_name} {raw_phase!r} is not in the controlled phase vocabulary.",
                )
                return []
            regional_phases[field_name] = normalized
        program = self.session.scalar(
            select(DevelopmentProgram).where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgram.drug_entity_id == drug.id,
                DevelopmentProgram.disease_entity_id == (disease.id if disease else None),
                DevelopmentProgram.organization_entity_id == (organization.id if organization else None),
            )
        )
        if program is None:
            program = DevelopmentProgram(
                tenant_id=self.tenant_id,
                drug_entity_id=drug.id,
                disease_entity_id=disease.id if disease else None,
                organization_entity_id=organization.id if organization else None,
                phase=phase,
            )
            self.session.add(program)
        incoming_status_date = _optional_datetime(payload.get("status_date"))
        should_update_current = program.status_date is None or (
            incoming_status_date is not None and _as_utc(incoming_status_date) >= _as_utc(program.status_date)
        )
        if should_update_current:
            program.phase = phase
            raw_status = cast(str | None, payload.get("status"))
            program.status_detail = raw_status
            # The model may emit the governed state directly; otherwise only an exact
            # controlled token in the free-text detail is promoted. Anything else stays
            # NULL rather than being bucketed by guesswork.
            governed_status = cast(str | None, payload.get("program_status"))
            fallback = raw_status.strip().lower() if raw_status else None
            program.program_status = governed_status or (
                fallback if fallback in {"active", "inactive", "unknown"} else None
            )
            program.modality = cast(str | None, payload.get("modality"))
            program.innovation_type = cast(str | None, payload.get("innovation_type"))
            program.therapeutic_area = cast(str | None, payload.get("therapeutic_area"))
            program.drug_category = cast(str | None, payload.get("drug_category"))
            program.mechanism_of_action = cast(str | None, payload.get("mechanism_of_action"))
            program.geography = cast(str | None, payload.get("geography"))
            program.status_date = incoming_status_date
            if payload.get("development_rights_regions"):
                program.development_rights_regions = list(payload["development_rights_regions"])
            if payload.get("commercialization_rights_regions"):
                program.commercialization_rights_regions = list(payload["commercialization_rights_regions"])
            if payload.get("program_tags"):
                program.program_tags = list(payload["program_tags"])
            self._sync_program_targets(program, targets, staged.source_document_id)
            self._sync_program_organizations(program, organizations, staged.source_document_id)
        for field_name, date_field in (
            ("global_phase", "global_phase_started_at"),
            ("china_phase", "china_phase_started_at"),
        ):
            regional_phase = regional_phases[field_name]
            incoming_phase_at = _optional_datetime(payload.get(date_field))
            current_phase_at = cast(datetime | None, getattr(program, date_field))
            if regional_phase is not None and _should_update_temporal_state(current_phase_at, incoming_phase_at):
                setattr(program, field_name, regional_phase.value)
                setattr(program, date_field, incoming_phase_at)
        program.status_history = _merge_program_status_history(
            program.status_history or [],
            cast(list[dict[str, Any]], payload.get("status_history") or []),
            current_phase=phase.value,
            current_status=cast(str | None, payload.get("status")),
            current_status_at=incoming_status_date,
            current_geography=cast(str | None, payload.get("geography")),
            source_document_id=staged.source_document_id,
        )
        program.milestones = _merge_program_milestones(
            program.milestones or [],
            cast(list[dict[str, Any]], payload.get("milestones") or []),
            source_document_id=staged.source_document_id,
        )
        program.source_document_id = staged.source_document_id
        for _, target in targets:
            self._relationship(drug, "has_target", target, staged)
        if disease:
            self._relationship(drug, "developed_for", disease, staged)
        for role, linked_organization, _, _ in organizations:
            predicate = "develops" if role == "originator" else f"program_{role}"
            self._relationship(linked_organization, predicate, drug, staged)
        self.session.flush()
        return [_projection("development_program", program.id)]

    def _sync_program_organizations(
        self,
        program: DevelopmentProgram,
        organizations: list[tuple[str, Entity, str | None, str | None]],
        source_document_id: str | None,
    ) -> None:
        """Append-only versioned organization set, mirroring the target set semantics."""
        self.session.flush()
        current_version = int(program.organization_set_version or 1)
        current = list(
            self.session.scalars(
                select(DevelopmentProgramOrganization)
                .where(
                    DevelopmentProgramOrganization.tenant_id == self.tenant_id,
                    DevelopmentProgramOrganization.program_id == program.id,
                    DevelopmentProgramOrganization.organization_set_version == current_version,
                )
                .order_by(DevelopmentProgramOrganization.position, DevelopmentProgramOrganization.id)
            )
        )
        desired = [
            (entity.id, role, country, org_type, position)
            for position, (role, entity, country, org_type) in enumerate(organizations)
        ]
        existing = [
            (item.organization_entity_id, item.role, item.country_region, item.organization_type, item.position)
            for item in current
        ]
        if existing == desired:
            if not current and organizations:
                self._append_program_organizations(program, current_version, organizations, source_document_id)
            return
        next_version = current_version + 1 if existing else current_version
        program.organization_set_version = next_version
        program.organization_entity_id = next(
            (entity.id for role, entity, _, _ in organizations if role == "originator"),
            None,
        )
        self._append_program_organizations(program, next_version, organizations, source_document_id)

    def _append_program_organizations(
        self,
        program: DevelopmentProgram,
        version: int,
        organizations: list[tuple[str, Entity, str | None, str | None]],
        source_document_id: str | None,
    ) -> None:
        for position, (role, entity, country, org_type) in enumerate(organizations):
            self.session.add(
                DevelopmentProgramOrganization(
                    tenant_id=self.tenant_id,
                    program_id=program.id,
                    organization_set_version=version,
                    organization_entity_id=entity.id,
                    role=role,
                    country_region=country,
                    organization_type=org_type,
                    position=position,
                    source_document_id=source_document_id,
                )
            )

    def _sync_program_targets(
        self,
        program: DevelopmentProgram,
        targets: list[tuple[ProgramTargetRole, Entity]],
        source_document_id: str | None,
    ) -> None:
        self.session.flush()
        current_version = int(program.target_set_version or 1)
        current = list(
            self.session.scalars(
                select(DevelopmentProgramTarget)
                .where(
                    DevelopmentProgramTarget.tenant_id == self.tenant_id,
                    DevelopmentProgramTarget.program_id == program.id,
                    DevelopmentProgramTarget.target_set_version == current_version,
                )
                .order_by(DevelopmentProgramTarget.position, DevelopmentProgramTarget.id)
            )
        )
        desired_signature = [(entity.id, role.value, position) for position, (role, entity) in enumerate(targets)]
        current_signature = [(item.target_entity_id, item.role.value, item.position) for item in current]
        if not current and program.target_entity_id:
            current_signature = [(program.target_entity_id, ProgramTargetRole.PRIMARY.value, 0)]
            if current_signature != desired_signature:
                self.session.add(
                    DevelopmentProgramTarget(
                        tenant_id=self.tenant_id,
                        program_id=program.id,
                        target_set_version=current_version,
                        target_entity_id=program.target_entity_id,
                        role=ProgramTargetRole.PRIMARY,
                        position=0,
                        source_document_id=program.source_document_id,
                    )
                )
        if current_signature == desired_signature:
            if not current and targets:
                self._append_program_targets(program, current_version, targets, source_document_id)
            program.target_combination_key = self._target_combination_key(targets)
            program.target_entity_id = next(
                (entity.id for role, entity in targets if role == ProgramTargetRole.PRIMARY),
                None,
            )
            return
        next_version = current_version + 1 if current_signature else current_version
        program.target_set_version = next_version
        program.target_combination_key = self._target_combination_key(targets)
        program.target_entity_id = next(
            (entity.id for role, entity in targets if role == ProgramTargetRole.PRIMARY),
            None,
        )
        self._append_program_targets(program, next_version, targets, source_document_id)

    def _append_program_targets(
        self,
        program: DevelopmentProgram,
        version: int,
        targets: list[tuple[ProgramTargetRole, Entity]],
        source_document_id: str | None,
    ) -> None:
        for position, (role, target) in enumerate(targets):
            self.session.add(
                DevelopmentProgramTarget(
                    tenant_id=self.tenant_id,
                    program_id=program.id,
                    target_set_version=version,
                    target_entity_id=target.id,
                    role=role,
                    position=position,
                    source_document_id=source_document_id,
                )
            )

    @staticmethod
    def _target_combination_key(targets: list[tuple[ProgramTargetRole, Entity]]) -> str | None:
        target_ids = sorted(entity.id for _, entity in targets)
        return "|".join(target_ids) if target_ids else None

    def _materialize_trial(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        trial_entity = self._entity(cast(dict[str, Any], payload["trial"]), staged.source_document_id)
        trial = self.session.scalar(
            select(ClinicalTrialProfile).where(
                ClinicalTrialProfile.tenant_id == self.tenant_id,
                ClinicalTrialProfile.registry_name == payload["registry_name"],
                ClinicalTrialProfile.registry_id == payload["registry_id"],
            )
        )
        if trial is None:
            trial = ClinicalTrialProfile(
                tenant_id=self.tenant_id,
                entity_id=trial_entity.id,
                registry_name=str(payload["registry_name"]),
                registry_id=str(payload["registry_id"]),
                official_title=str(payload["official_title"]),
            )
            self.session.add(trial)
            self.session.flush()
        elif trial.entity_id != trial_entity.id:
            raise GovernanceError("Clinical trial registry identifier is already assigned to another entity")
        trial.official_title = str(payload["official_title"])
        trial.acronym = cast(str | None, payload.get("acronym"))
        trial.initiation_type = cast(str | None, payload.get("initiation_type"))
        trial.therapy_lines = _merge_strings([], list(payload.get("therapy_lines") or []), limit=12)
        trial.overall_status = cast(str | None, payload.get("overall_status"))
        trial.phases = list(payload.get("phases") or [])
        trial.study_type = cast(str | None, payload.get("study_type"))
        trial.enrollment = cast(int | None, payload.get("enrollment"))
        trial.start_date = _optional_datetime(payload.get("start_date"))
        trial.start_date_precision = cast(str | None, payload.get("start_date_precision"))
        trial.completion_date = _optional_datetime(payload.get("completion_date"))
        trial.completion_date_precision = cast(str | None, payload.get("completion_date_precision"))
        trial.conditions = list(payload.get("conditions") or [])
        trial.interventions = [dict(item) for item in payload.get("interventions") or []]
        trial.sponsors = [dict(item) for item in payload.get("sponsors") or []]
        trial.locations = [dict(item) for item in payload.get("locations") or []]
        trial.study_design = dict(payload.get("study_design") or {})
        trial.eligibility = dict(payload.get("eligibility") or {})
        trial.arms = [dict(item) for item in payload.get("arms") or []]
        trial.outcomes = [dict(item) for item in payload.get("outcomes") or []]
        trial.result_evaluation = cast(str | None, payload.get("result_evaluation"))
        trial.results_first_posted = _optional_datetime(payload.get("results_first_posted"))
        trial.last_update_posted = _optional_datetime(payload.get("last_update_posted"))
        trial.status_history = _merge_trial_status_history(
            trial.status_history or [],
            cast(list[dict[str, Any]], payload.get("status_history") or []),
            current_status=trial.overall_status,
            current_status_at=trial.last_update_posted,
            source_document_id=staged.source_document_id,
        )
        trial.source_document_id = staged.source_document_id
        for reference in payload.get("linked_entities") or []:
            linked = self._entity(cast(dict[str, Any], reference), staged.source_document_id)
            self._relationship(trial_entity, "trial_links_entity", linked, staged)
        self._materialize_trial_entity_roles(trial, trial_entity, staged, payload)
        if self._source_type_for_document(staged.source_document_id) == DataSourceType.CLINICALTRIALS_GOV:
            self._materialize_official_trial_intervention_roles(trial, trial_entity, staged, payload)
        self._materialize_trial_result_disclosures(trial, staged, payload)
        trial.has_results = any(outcome.get("results") for outcome in trial.outcomes) or bool(
            self.session.scalar(
                select(ClinicalTrialResultDisclosure.id)
                .where(
                    ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                    ClinicalTrialResultDisclosure.trial_id == trial.id,
                )
                .limit(1)
            )
        )
        self.session.flush()
        return [_projection("clinical_trial", trial.id)]

    def _materialize_trial_entity_roles(
        self,
        trial: ClinicalTrialProfile,
        trial_entity: Entity,
        staged: StagedFact,
        payload: dict[str, Any],
    ) -> None:
        for item in payload.get("entity_roles") or []:
            role = TrialEntityRole(str(item["role"]))
            entity = self._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id)
            association = self.session.scalar(
                select(ClinicalTrialEntityRole).where(
                    ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                    ClinicalTrialEntityRole.trial_id == trial.id,
                    ClinicalTrialEntityRole.entity_id == entity.id,
                    ClinicalTrialEntityRole.role == role.value,
                )
            )
            if association is None:
                self.session.add(
                    ClinicalTrialEntityRole(
                        tenant_id=self.tenant_id,
                        trial_id=trial.id,
                        entity_id=entity.id,
                        role=role.value,
                        source_document_id=staged.source_document_id,
                    )
                )
            else:
                association.source_document_id = staged.source_document_id
            self._relationship(trial_entity, "trial_links_entity", entity, staged)
            self._relationship(trial_entity, f"trial_{role.value}", entity, staged)

    def _materialize_official_trial_intervention_roles(
        self,
        trial: ClinicalTrialProfile,
        trial_entity: Entity,
        staged: StagedFact,
        payload: dict[str, Any],
    ) -> None:
        matched_entities: list[Entity] = []
        seen_entity_ids: set[str] = set()
        for item in payload.get("interventions") or []:
            if not isinstance(item, dict) or str(item.get("type") or "").casefold() not in {
                "drug",
                "biological",
            }:
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            candidates = list(
                self.session.scalars(
                    select(Entity)
                    .where(
                        Entity.tenant_id == self.tenant_id,
                        Entity.entity_type == EntityType.DRUG,
                        Entity.normalized_name == normalize_name(name),
                        Entity.review_status == ReviewStatus.VERIFIED,
                    )
                    .order_by(Entity.id)
                    .limit(2)
                )
            )
            if len(candidates) != 1 or candidates[0].id in seen_entity_ids:
                continue
            seen_entity_ids.add(candidates[0].id)
            matched_entities.append(candidates[0])

        for position, entity in enumerate(matched_entities):
            role = TrialEntityRole.INVESTIGATIONAL_DRUG if position == 0 else TrialEntityRole.COMBINATION_DRUG
            association = self.session.scalar(
                select(ClinicalTrialEntityRole).where(
                    ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                    ClinicalTrialEntityRole.trial_id == trial.id,
                    ClinicalTrialEntityRole.entity_id == entity.id,
                    ClinicalTrialEntityRole.role == role.value,
                )
            )
            if association is None:
                self.session.add(
                    ClinicalTrialEntityRole(
                        tenant_id=self.tenant_id,
                        trial_id=trial.id,
                        entity_id=entity.id,
                        role=role.value,
                        source_document_id=staged.source_document_id,
                    )
                )
            else:
                association.source_document_id = staged.source_document_id
            self._relationship(trial_entity, "trial_links_entity", entity, staged)
            self._relationship(trial_entity, f"trial_{role.value}", entity, staged)

    def _materialize_trial_result_disclosures(
        self,
        trial: ClinicalTrialProfile,
        staged: StagedFact,
        payload: dict[str, Any],
    ) -> None:
        for item in payload.get("result_disclosures") or []:
            disclosure_key = str(item["disclosure_key"])
            version = int(item["version"])
            disclosure = self.session.scalar(
                select(ClinicalTrialResultDisclosure).where(
                    ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                    ClinicalTrialResultDisclosure.trial_id == trial.id,
                    ClinicalTrialResultDisclosure.disclosure_key == disclosure_key,
                    ClinicalTrialResultDisclosure.version == version,
                )
            )
            if disclosure is None:
                disclosure = ClinicalTrialResultDisclosure(
                    tenant_id=self.tenant_id,
                    trial_id=trial.id,
                    disclosure_key=disclosure_key,
                    version=version,
                    disclosure_type=str(item["disclosure_type"]),
                    title=str(item["title"]),
                    disclosed_at=_required_datetime(item["disclosed_at"], "disclosed_at"),
                )
                self.session.add(disclosure)
            citation = cast(dict[str, Any], item["citation"])
            disclosure.disclosure_type = str(item["disclosure_type"])
            disclosure.external_id = cast(str | None, item.get("external_id"))
            disclosure.title = str(item["title"])
            disclosure.disclosed_at = _required_datetime(item["disclosed_at"], "disclosed_at")
            disclosure.conference_name = cast(str | None, item.get("conference_name"))
            disclosure.is_key_result = bool(item.get("is_key_result", False))
            disclosure.result_evaluation = cast(str | None, item.get("result_evaluation"))
            disclosure.source_locator = cast(str | None, citation.get("locator"))
            disclosure.source_quote = str(citation["quote"])
            disclosure.source_document_id = staged.source_document_id

    def _materialize_patent(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        patent_entity = self._entity(cast(dict[str, Any], payload["patent"]), staged.source_document_id)
        linked_entities = [
            self._entity(cast(dict[str, Any], reference), staged.source_document_id)
            for reference in payload.get("linked_entities") or []
        ]
        patent = self.session.scalar(
            select(PatentFamily).where(
                PatentFamily.tenant_id == self.tenant_id,
                PatentFamily.family_identifier == payload["family_identifier"],
            )
        )
        if patent is None:
            patent = PatentFamily(
                tenant_id=self.tenant_id,
                entity_id=patent_entity.id,
                family_identifier=str(payload["family_identifier"]),
                title=str(payload["title"]),
            )
            self.session.add(patent)
        patent.title = str(payload["title"])
        patent.applicants = _merge_strings(patent.applicants or [], list(payload.get("applicants") or []), limit=100)
        patent.inventors = _merge_strings(patent.inventors or [], list(payload.get("inventors") or []), limit=200)
        patent.publications = _merge_patent_publications(
            patent.publications or [],
            cast(list[dict[str, Any] | str], payload.get("publications") or []),
        )
        incoming_priority_date = _optional_datetime(payload.get("priority_date"))
        if incoming_priority_date is not None and (
            patent.priority_date is None or _as_utc(incoming_priority_date) < _as_utc(patent.priority_date)
        ):
            patent.priority_date = incoming_priority_date
        incoming_status_at = _optional_datetime(payload.get("legal_status_at"))
        should_update_status = _should_update_temporal_state(patent.legal_status_at, incoming_status_at)
        if should_update_status and payload.get("legal_status") is not None:
            patent.legal_status = cast(str | None, payload.get("legal_status"))
            patent.legal_status_at = incoming_status_at
            if payload.get("expiration_date") is not None:
                patent.expiration_date = _optional_datetime(payload.get("expiration_date"))
        patent.legal_events = _merge_patent_legal_events(
            patent.legal_events or [],
            cast(list[dict[str, Any]], payload.get("legal_events") or []),
            current_status=cast(str | None, payload.get("legal_status")),
            current_status_at=incoming_status_at,
            source_document_id=staged.source_document_id,
        )
        patent.independent_claims = _merge_patent_claims(
            patent.independent_claims or [],
            cast(list[dict[str, Any]], payload.get("independent_claims") or []),
            source_document_id=staged.source_document_id,
        )
        patent.linked_entity_ids = sorted(
            {*(patent.linked_entity_ids or []), *(entity.id for entity in linked_entities)}
        )
        patent.source_document_id = staged.source_document_id
        for linked in linked_entities:
            self._relationship(patent_entity, "patent_links_entity", linked, staged)
        self.session.flush()
        return [_projection("patent_family", patent.id)]

    def _materialize_deal(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        deal_entity = self._entity(cast(dict[str, Any], payload["deal"]), staged.source_document_id)
        legacy_parties = [
            self._entity(cast(dict[str, Any], reference), staged.source_document_id)
            for reference in payload.get("parties") or []
        ]
        role_rows: list[tuple[Entity, dict[str, Any]]] = []
        for association in payload.get("party_roles") or []:
            association_payload = cast(dict[str, Any], association)
            role_rows.append(
                (
                    self._entity(
                        cast(dict[str, Any], association_payload["party"]),
                        staged.source_document_id,
                    ),
                    association_payload,
                )
            )
        parties_by_id = {entity.id: entity for entity in legacy_parties}
        parties_by_id.update({entity.id: entity for entity, _association in role_rows})
        parties = list(parties_by_id.values())

        legacy_assets = [
            self._entity(cast(dict[str, Any], reference), staged.source_document_id)
            for reference in payload.get("assets") or []
        ]
        staged_assets: list[tuple[Entity, dict[str, Any]]] = []
        for association in payload.get("asset_stages") or []:
            association_payload = cast(dict[str, Any], association)
            staged_assets.append(
                (
                    self._entity(
                        cast(dict[str, Any], association_payload["asset"]),
                        staged.source_document_id,
                    ),
                    association_payload,
                )
            )
        assets_by_id = {entity.id: entity for entity in legacy_assets}
        assets_by_id.update({entity.id: entity for entity, _association in staged_assets})
        assets = list(assets_by_id.values())
        deal = self.session.scalar(
            select(DealProfile).where(
                DealProfile.tenant_id == self.tenant_id,
                DealProfile.entity_id == deal_entity.id,
            )
        )
        if deal is None:
            deal = DealProfile(
                tenant_id=self.tenant_id,
                entity_id=deal_entity.id,
                deal_type=str(payload["deal_type"]),
            )
            self.session.add(deal)
        deal.deal_type = str(payload["deal_type"])
        deal.status = str(payload.get("status") or DealStatus.UNKNOWN.value)
        deal.direction = str(payload.get("direction") or DealDirection.UNDISCLOSED.value)
        deal.direction_reference_jurisdiction = cast(
            str | None,
            payload.get("direction_reference_jurisdiction"),
        )
        deal.parties = [
            {"entity_id": entity.id, "name": entity.name, "entity_type": entity.entity_type.value} for entity in parties
        ]
        deal.asset_entity_ids = [entity.id for entity in assets]
        deal.announced_at = _optional_datetime(payload.get("announced_at"))
        deal.terminated_at = _optional_datetime(payload.get("terminated_at"))
        deal.source_updated_at = _optional_datetime(payload.get("source_updated_at"))
        deal.territory = cast(str | None, payload.get("territory"))
        deal.upfront_amount = cast(float | None, payload.get("upfront_amount"))
        deal.total_potential_amount = cast(float | None, payload.get("total_potential_amount"))
        deal.currency = cast(str | None, payload.get("currency"))
        deal.terms = cast(dict[str, Any], payload.get("terms") or {})
        deal.source_document_id = staged.source_document_id
        self.session.flush()

        self.session.execute(
            delete(DealPartyAssociation).where(
                DealPartyAssociation.tenant_id == self.tenant_id,
                DealPartyAssociation.deal_id == deal.id,
            )
        )
        self.session.execute(
            delete(DealAssetAssociation).where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.deal_id == deal.id,
            )
        )
        self.session.execute(
            delete(DealRight).where(
                DealRight.tenant_id == self.tenant_id,
                DealRight.deal_id == deal.id,
            )
        )

        explicit_role_party_ids = {entity.id for entity, _association in role_rows}
        for party in legacy_parties:
            if party.id not in explicit_role_party_ids:
                role_rows.append((party, {"role": DealPartyRole.OTHER.value}))
        for party, association in role_rows:
            role = str(association["role"])
            self.session.add(
                DealPartyAssociation(
                    tenant_id=self.tenant_id,
                    deal_id=deal.id,
                    party_entity_id=party.id,
                    role=role,
                    country_region=cast(str | None, association.get("country_region")),
                    organization_type=cast(str | None, association.get("organization_type")),
                    source_document_id=staged.source_document_id,
                )
            )
            self._relationship(deal_entity, f"deal_party_{role}", party, staged)

        staged_asset_ids = {entity.id for entity, _association in staged_assets}
        staged_assets.extend(
            (asset, {"development_phase_at_transaction": None})
            for asset in legacy_assets
            if asset.id not in staged_asset_ids
        )
        for asset, association in staged_assets:
            self.session.add(
                DealAssetAssociation(
                    tenant_id=self.tenant_id,
                    deal_id=deal.id,
                    asset_entity_id=asset.id,
                    development_phase_at_transaction=cast(
                        str | None,
                        association.get("development_phase_at_transaction"),
                    ),
                    source_document_id=staged.source_document_id,
                )
            )

        for right_payload in payload.get("rights") or []:
            right = cast(dict[str, Any], right_payload)
            holder = self._entity(cast(dict[str, Any], right["holder"]), staged.source_document_id)
            self.session.add(
                DealRight(
                    tenant_id=self.tenant_id,
                    deal_id=deal.id,
                    holder_entity_id=holder.id,
                    right_type=str(right["right_type"]),
                    territory=str(right["territory"]),
                    exclusive=cast(bool | None, right.get("exclusive")),
                    scope_description=cast(str | None, right.get("scope_description")),
                    source_document_id=staged.source_document_id,
                )
            )
            self._relationship(deal_entity, "deal_right_holder", holder, staged)
        for party in parties:
            self._relationship(deal_entity, "deal_party", party, staged)
        for asset in assets:
            self._relationship(deal_entity, "deal_asset", asset, staged)
        self.session.flush()
        return [_projection("deal", deal.id)]

    def _materialize_regulatory(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        subject = self._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
        indication = self._optional_entity(payload.get("indication"), staged.source_document_id)
        organization = self._optional_entity(payload.get("organization"), staged.source_document_id)
        agency = str(payload["agency"])
        event_identifier = str(payload["event_identifier"])
        event = self.session.scalar(
            select(RegulatoryEvent).where(
                RegulatoryEvent.tenant_id == self.tenant_id,
                RegulatoryEvent.agency == agency,
                RegulatoryEvent.event_identifier == event_identifier,
            )
        )
        if event is None:
            event = RegulatoryEvent(
                tenant_id=self.tenant_id,
                subject_entity_id=subject.id,
                agency=agency,
                jurisdiction=str(payload["jurisdiction"]),
                event_identifier=event_identifier,
                event_type=str(payload["event_type"]),
                title=str(payload["title"]),
            )
            self.session.add(event)
        elif event.subject_entity_id != subject.id:
            raise GovernanceError("Regulatory event identifier is already assigned to another normalized entity")
        event.jurisdiction = str(payload["jurisdiction"])
        event.application_number = cast(str | None, payload.get("application_number"))
        event.event_type = str(payload["event_type"])
        event.status = cast(str | None, payload.get("status"))
        event.title = str(payload["title"])
        event.decision_date = _optional_datetime(payload.get("decision_date"))
        event.designation_type = cast(str | None, payload.get("designation_type"))
        event.label_change_type = cast(str | None, payload.get("label_change_type"))
        event.label_version = cast(str | None, payload.get("label_version"))
        event.label_effective_at = _optional_datetime(payload.get("label_effective_at"))
        event.approved_population = cast(str | None, payload.get("approved_population"))
        event.line_of_therapy = cast(str | None, payload.get("line_of_therapy"))
        event.biomarker = cast(str | None, payload.get("biomarker"))
        event.route_of_administration = cast(str | None, payload.get("route_of_administration"))
        event.dosage_form = cast(str | None, payload.get("dosage_form"))
        event.has_boxed_warning = cast(bool | None, payload.get("has_boxed_warning"))
        event.safety_signal_type = cast(str | None, payload.get("safety_signal_type"))
        event.safety_term = cast(str | None, payload.get("safety_term"))
        event.safety_severity = cast(str | None, payload.get("safety_severity"))
        event.safety_status = cast(str | None, payload.get("safety_status"))
        event.safety_identified_at = _optional_datetime(payload.get("safety_identified_at"))
        event.safety_confirmed_at = _optional_datetime(payload.get("safety_confirmed_at"))
        event.safety_resolved_at = _optional_datetime(payload.get("safety_resolved_at"))
        event.affected_population = cast(str | None, payload.get("affected_population"))
        event.risk_actions = [str(action) for action in payload.get("risk_actions") or []]
        event.source_updated_at = _optional_datetime(payload.get("source_updated_at"))
        event.indication_entity_id = indication.id if indication else None
        event.organization_entity_id = organization.id if organization else None
        event.details = dict(payload.get("details") or {})
        event.source_document_id = staged.source_document_id
        if indication:
            self._relationship(subject, "regulatory_indication", indication, staged)
        if organization:
            self._relationship(organization, "regulatory_sponsor", subject, staged)
        self.session.flush()
        return [_projection("regulatory_event", event.id)]

    def _materialize_epidemiology(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        disease = self._entity(cast(dict[str, Any], payload["disease"]), staged.source_document_id)
        publisher = self._optional_entity(payload.get("publisher"), staged.source_document_id)
        population: PatientPopulation | None = None
        population_payload = payload.get("patient_population")
        if isinstance(population_payload, dict):
            population_key = str(population_payload["population_key"])
            population = self.session.scalar(
                select(PatientPopulation).where(
                    PatientPopulation.tenant_id == self.tenant_id,
                    PatientPopulation.population_key == population_key,
                )
            )
            if population is None:
                population = PatientPopulation(
                    tenant_id=self.tenant_id,
                    population_key=population_key,
                    name=str(population_payload["name"]),
                )
                self.session.add(population)
                self.session.flush()
            population.name = str(population_payload["name"])
            population.description = cast(str | None, population_payload.get("description"))
            population.attributes = dict(population_payload.get("attributes") or {})
            population.review_status = ReviewStatus.VERIFIED
            population.source_document_id = staged.source_document_id
            linked_entities: dict[tuple[str, str], Entity] = {(disease.id, "disease"): disease}
            for target_payload in cast(list[dict[str, Any]], population_payload.get("targets") or []):
                target = self._entity(target_payload, staged.source_document_id)
                linked_entities[(target.id, "target")] = target
            for (entity_id, relationship), entity in linked_entities.items():
                existing_link = self.session.scalar(
                    select(PatientPopulationEntityLink).where(
                        PatientPopulationEntityLink.tenant_id == self.tenant_id,
                        PatientPopulationEntityLink.patient_population_id == population.id,
                        PatientPopulationEntityLink.entity_id == entity_id,
                        PatientPopulationEntityLink.relationship == relationship,
                    )
                )
                if existing_link is None:
                    self.session.add(
                        PatientPopulationEntityLink(
                            tenant_id=self.tenant_id,
                            patient_population_id=population.id,
                            entity_id=entity.id,
                            relationship=relationship,
                            source_document_id=staged.source_document_id,
                        )
                    )
        observation_identifier = str(payload["observation_identifier"])
        observation = self.session.scalar(
            select(EpidemiologyObservation).where(
                EpidemiologyObservation.tenant_id == self.tenant_id,
                EpidemiologyObservation.observation_identifier == observation_identifier,
            )
        )
        if observation is None:
            observation = EpidemiologyObservation(
                tenant_id=self.tenant_id,
                observation_identifier=observation_identifier,
                disease_entity_id=disease.id,
                measure=str(payload["measure"]),
                value=Decimal(str(payload["value"])),
                unit=str(payload["unit"]),
                geography=str(payload["geography"]),
                population_scope=str(payload["population_scope"]),
            )
            self.session.add(observation)
        elif observation.disease_entity_id != disease.id:
            raise GovernanceError("Epidemiology observation identifier is already assigned to another disease")
        observation.measure = str(payload["measure"])
        observation.value = Decimal(str(payload["value"]))
        observation.lower_bound = _optional_decimal(payload.get("lower_bound"))
        observation.upper_bound = _optional_decimal(payload.get("upper_bound"))
        observation.unit = str(payload["unit"])
        observation.geography = str(payload["geography"])
        observation.population_scope = str(payload["population_scope"])
        if population is not None:
            observation.patient_population_id = population.id
        observation.age_group = cast(str | None, payload.get("age_group"))
        observation.sex = cast(str | None, payload.get("sex"))
        observation.period_start = _optional_datetime(payload.get("period_start"))
        observation.period_end = _optional_datetime(payload.get("period_end"))
        observation.sample_size = _optional_decimal(payload.get("sample_size"))
        observation.methodology = cast(str | None, payload.get("methodology"))
        observation.publisher_entity_id = publisher.id if publisher else None
        observation.source_document_id = staged.source_document_id
        if publisher:
            self._relationship(publisher, "epidemiology_publisher", disease, staged)
        self.session.flush()
        projections = [_projection("epidemiology_observation", observation.id)]
        if population is not None:
            projections.append(_projection("patient_population", population.id))
        return projections

    def _materialize_news(self, staged: StagedFact, payload: dict[str, Any]) -> list[dict[str, str]]:
        publisher = self._optional_entity(payload.get("publisher"), staged.source_document_id)
        related_entities = [
            self._entity(item, staged.source_document_id)
            for item in cast(list[dict[str, Any]], payload.get("related_entities") or [])
        ]
        event_identifier = str(payload["event_identifier"])
        event = self.session.scalar(
            select(NewsEvent).where(
                NewsEvent.tenant_id == self.tenant_id,
                NewsEvent.event_identifier == event_identifier,
            )
        )
        if event is None:
            event = NewsEvent(
                tenant_id=self.tenant_id,
                event_identifier=event_identifier,
                event_type=str(payload["event_type"]),
                title=str(payload["title"]),
            )
            self.session.add(event)
        event.event_type = str(payload["event_type"])
        event.title = str(payload["title"])
        event.summary = cast(str | None, payload.get("summary"))
        event.published_at = _optional_datetime(payload.get("published_at"))
        event.language = cast(str | None, payload.get("language"))
        event.publisher_entity_id = publisher.id if publisher else None
        event.related_entity_ids = [entity.id for entity in related_entities]
        event.canonical_url = str(payload["canonical_url"]) if payload.get("canonical_url") else None
        event.venue = cast(str | None, payload.get("venue"))
        event.details = dict(payload.get("details") or {})
        event.source_document_id = staged.source_document_id
        for related in related_entities:
            if publisher:
                self._relationship(publisher, "announced_about", related, staged)
        self.session.flush()
        return [_projection("news_event", event.id)]

    def _optional_entity(self, value: Any, source_document_id: str | None) -> Entity | None:
        return self._entity(cast(dict[str, Any], value), source_document_id) if isinstance(value, dict) else None

    def _relationship(self, subject: Entity, predicate: str, object_entity: Entity, staged: StagedFact) -> None:
        relationship = self.session.scalar(
            select(Relationship).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.subject_id == subject.id,
                Relationship.predicate == predicate,
                Relationship.object_id == object_entity.id,
                Relationship.valid_from.is_(None),
            )
        )
        evidence = {"source_document_id": staged.source_document_id, "staged_fact_id": staged.id}
        if relationship is None:
            self.session.add(
                Relationship(
                    tenant_id=self.tenant_id,
                    subject_id=subject.id,
                    predicate=predicate,
                    object_id=object_entity.id,
                    attributes={"evidence": [evidence]},
                    review_status=ReviewStatus.VERIFIED,
                )
            )
            return
        evidence_items = list(relationship.attributes.get("evidence") or [])
        if evidence not in evidence_items:
            evidence_items.append(evidence)
            relationship.attributes = {**relationship.attributes, "evidence": evidence_items}
        relationship.review_status = ReviewStatus.VERIFIED

    @staticmethod
    def _defer_projection(staged: StagedFact, code: str, message: str) -> None:
        findings = list(staged.quality_findings)
        if not any(item.get("code") == code for item in findings):
            findings.append({"code": code, "severity": "warning", "message": message})
            staged.quality_findings = findings

    def _entity(self, reference: dict[str, Any], source_document_id: str | None) -> Entity:
        return EntityIdentityService(self.session, self.tenant_id).resolve_or_create(
            reference,
            source_document_id=source_document_id,
            allow_unverified_trusted_identifiers=self._allow_unverified_trusted_identifiers(source_document_id),
        )

    def _allow_unverified_trusted_identifiers(self, source_document_id: str | None) -> bool:
        if not source_document_id:
            return False
        cached = self._trusted_identity_mode_cache.get(source_document_id)
        if cached is not None:
            return cached
        source_type = self._source_type_for_document(source_document_id)
        allowed = source_type in {DataSourceType.CHEMBL, DataSourceType.CLINICALTRIALS_GOV}
        self._trusted_identity_mode_cache[source_document_id] = allowed
        return allowed

    def _source_type_for_document(self, source_document_id: str | None) -> DataSourceType | None:
        if not source_document_id:
            return None
        if source_document_id in self._source_type_cache:
            return self._source_type_cache[source_document_id]
        source_type = self.session.scalar(
            select(DataSource.source_type)
            .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
            .join(SourceVersion, SourceVersion.source_asset_id == SourceAsset.id)
            .where(
                DataSource.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
                SourceVersion.tenant_id == self.tenant_id,
                SourceVersion.source_document_id == source_document_id,
            )
        )
        self._source_type_cache[source_document_id] = source_type
        return source_type

    def _run_summary(self, run: ExtractionRun) -> dict[str, int | str]:
        statuses = list(
            self.session.scalars(
                select(StagedFact.status).where(
                    StagedFact.tenant_id == self.tenant_id,
                    StagedFact.extraction_run_id == run.id,
                )
            )
        )
        summary: dict[str, int | str] = {"run_id": run.id, "fact_count": len(statuses)}
        for status in GovernanceStatus:
            summary[status.value] = statuses.count(status)
        return summary


def _segments(text: str, max_chars: int, overlap: int = 1000) -> list[DocumentSegment]:
    if max_chars <= overlap:
        raise GovernanceError("AI_MAX_INPUT_CHARS must be larger than the extraction overlap")
    if len(text) <= max_chars:
        return [DocumentSegment(text=text, start_char=0, end_char=len(text))]
    segments: list[DocumentSegment] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        segments.append(DocumentSegment(text=text[start:end], start_char=start, end_char=end))
        if end == len(text):
            break
        start = end - overlap
    return segments


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GovernanceError("Validated governance date is not ISO 8601") from exc
    raise GovernanceError("Validated governance date has an invalid type")


def _required_datetime(value: Any, field_name: str) -> datetime:
    parsed = _optional_datetime(value)
    if parsed is None:
        raise GovernanceError(f"{field_name} is required")
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _should_update_temporal_state(current_at: datetime | None, incoming_at: datetime | None) -> bool:
    return current_at is None or (incoming_at is not None and _as_utc(incoming_at) >= _as_utc(current_at))


def _merge_program_status_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_phase: str,
    current_status: str | None,
    current_status_at: datetime | None,
    current_geography: str | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        phase = str(raw_event.get("phase") or "").strip()
        effective_at = _optional_datetime(raw_event.get("effective_at"))
        if not phase or effective_at is None:
            continue
        timestamp = effective_at.isoformat()
        status = str(raw_event.get("status") or "").strip()
        geography = str(raw_event.get("geography") or "").strip()
        event = {
            "phase": phase,
            "status": status or None,
            "effective_at": timestamp,
            "geography": geography or None,
            "reason": raw_event.get("reason"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(phase, status, timestamp, geography)] = event
    if current_status_at:
        timestamp = current_status_at.isoformat()
        status = (current_status or "").strip()
        geography = (current_geography or "").strip()
        events.setdefault(
            (current_phase, status, timestamp, geography),
            {
                "phase": current_phase,
                "status": status or None,
                "effective_at": timestamp,
                "geography": geography or None,
                "reason": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(
        events.values(),
        key=lambda event: (event["effective_at"], event["phase"], event.get("geography") or ""),
    )[-500:]


def _merge_program_milestones(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        milestone_type = str(raw_event.get("milestone_type") or "").strip()
        title = str(raw_event.get("title") or "").strip()
        occurred_at = _optional_datetime(raw_event.get("occurred_at"))
        if not milestone_type or not title or occurred_at is None:
            continue
        timestamp = occurred_at.isoformat()
        geography = str(raw_event.get("geography") or "").strip()
        event = {
            "milestone_type": milestone_type,
            "title": title,
            "occurred_at": timestamp,
            "geography": geography or None,
            "description": raw_event.get("description"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(milestone_type, title, timestamp, geography)] = event
    return sorted(
        events.values(),
        key=lambda event: (event["occurred_at"], event["milestone_type"], event["title"]),
    )[-500:]


def _merge_strings(existing: list[str], incoming: list[str], *, limit: int) -> list[str]:
    values = {str(value).strip() for value in [*existing, *incoming] if str(value).strip()}
    return sorted(values, key=str.casefold)[:limit]


def _merge_patent_publications(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any] | str],
) -> list[dict[str, Any]]:
    publications: dict[str, dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        item = {"publication_number": raw} if isinstance(raw, str) else dict(raw)
        publication_number = str(item.get("publication_number") or "").strip()
        if not publication_number:
            continue
        normalized = {
            "publication_number": publication_number,
            "application_number": item.get("application_number"),
            "jurisdiction": item.get("jurisdiction"),
            "publication_date": _iso_datetime(item.get("publication_date")),
            "grant_date": _iso_datetime(item.get("grant_date")),
        }
        previous = publications.get(publication_number)
        publications[publication_number] = {
            key: value if value is not None else (previous or {}).get(key) for key, value in normalized.items()
        }
    return sorted(publications.values(), key=lambda item: item["publication_number"])[:500]


def _merge_patent_legal_events(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_status: str | None,
    current_status_at: datetime | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        event_type = str(raw.get("event_type") or "").strip()
        occurred_at = _optional_datetime(raw.get("occurred_at"))
        if not event_type or occurred_at is None:
            continue
        status = str(raw.get("status") or "").strip()
        jurisdiction = str(raw.get("jurisdiction") or "").strip()
        timestamp = occurred_at.isoformat()
        event = {
            "event_type": event_type,
            "status": status or None,
            "occurred_at": timestamp,
            "jurisdiction": jurisdiction or None,
            "publication_number": raw.get("publication_number"),
            "description": raw.get("description"),
            "source_document_id": raw.get("source_document_id") or source_document_id,
        }
        events[(event_type, status, timestamp, jurisdiction)] = event
    if current_status and current_status_at:
        timestamp = current_status_at.isoformat()
        events.setdefault(
            ("status_update", current_status, timestamp, ""),
            {
                "event_type": "status_update",
                "status": current_status,
                "occurred_at": timestamp,
                "jurisdiction": None,
                "publication_number": None,
                "description": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(events.values(), key=lambda event: (event["occurred_at"], event["event_type"]))[-1000:]


def _merge_patent_claims(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    claims: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        claim_number = str(raw.get("claim_number") or "").strip()
        claim_type = str(raw.get("claim_type") or "").strip()
        summary = str(raw.get("summary") or "").strip()
        if not claim_number or not claim_type or not summary:
            continue
        claims[(claim_number, claim_type)] = {
            "claim_number": claim_number,
            "claim_type": claim_type,
            "summary": summary,
            "scope": raw.get("scope"),
            "source_document_id": raw.get("source_document_id") or source_document_id,
        }
    return sorted(claims.values(), key=lambda claim: (claim["claim_number"], claim["claim_type"]))[:100]


def _iso_datetime(value: Any) -> str | None:
    parsed = _optional_datetime(value)
    return parsed.isoformat() if parsed is not None else None


def _merge_trial_status_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_status: str | None,
    current_status_at: datetime | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        status = str(raw_event.get("status") or "").strip()
        effective_at = _optional_datetime(raw_event.get("effective_at"))
        if not status or effective_at is None:
            continue
        timestamp = effective_at.isoformat()
        event = {
            "status": status,
            "effective_at": timestamp,
            "reason": raw_event.get("reason"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(status, timestamp)] = event
    if current_status and current_status_at:
        timestamp = current_status_at.isoformat()
        events.setdefault(
            (current_status, timestamp),
            {
                "status": current_status,
                "effective_at": timestamp,
                "reason": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(events.values(), key=lambda event: (event["effective_at"], event["status"]))[-500:]


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError) as exc:
        raise GovernanceError("Validated governance number has an invalid value") from exc


def _deduplicate_prepared_facts(facts: Iterable[PreparedSegmentFact]) -> list[PreparedSegmentFact]:
    unique: dict[str, PreparedSegmentFact] = {}
    for fact in facts:
        key = _prepared_fact_key(fact.prepared)
        previous = unique.get(key)
        candidate_rank = (fact.quote_verified, fact.prepared.fact.citation.confidence)
        previous_rank = (
            (
                previous.quote_verified,
                previous.prepared.fact.citation.confidence,
            )
            if previous is not None
            else None
        )
        if previous_rank is None or candidate_rank > previous_rank:
            unique[key] = fact
    return list(unique.values())


def _quote_source_match(quote: str, segment: DocumentSegment) -> SourceQuoteMatch | None:
    stripped = quote.strip()
    if not stripped:
        return None
    start = segment.text.find(stripped)
    end = start + len(stripped)
    if start < 0:
        tokens = stripped.split()
        if not tokens:
            return None
        match = re.search(r"\s+".join(re.escape(token) for token in tokens), segment.text, flags=re.IGNORECASE)
        if match is None:
            return None
        start, end = match.span()
    return SourceQuoteMatch(
        locator=f"chars={segment.start_char + start}-{segment.start_char + end}",
        quote=segment.text[start:end],
    )


def _model_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate: Decimal,
    output_rate: Decimal,
) -> Decimal:
    return (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / MILLION_TOKENS


def _extraction_audit(
    segment_audits: list[dict[str, Any]],
    settings: Settings,
    estimated_cost: Decimal,
    *,
    policy_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "governance_schema_version": SCHEMA_VERSION,
        "policy_sha256": policy_sha256 or governance_policy_sha256(settings),
        "segments": segment_audits,
        "budget": {
            "max_document_chars": settings.ai_max_document_chars,
            "max_segments_per_document": settings.ai_max_segments_per_document,
            "max_input_tokens": settings.ai_max_document_input_tokens,
            "max_output_tokens": settings.ai_max_document_output_tokens,
            "max_output_tokens_per_segment": settings.ai_max_output_tokens_per_segment,
            "max_response_bytes": settings.ai_max_response_bytes,
            "input_cost_per_million_tokens": format(settings.ai_input_cost_per_million_tokens, "f"),
            "output_cost_per_million_tokens": format(settings.ai_output_cost_per_million_tokens, "f"),
            "max_document_cost": format(settings.ai_max_document_cost, "f"),
            "estimated_cost": format(estimated_cost, "f"),
        },
    }


def _profiled_model_text(
    text: str,
    source_profile: str | None,
    *,
    max_string_chars: int = 4000,
) -> tuple[str, dict[str, str] | None]:
    if source_profile is None:
        return text, None
    if source_profile == "pubmed":
        return text, None
    if source_profile != "clinicaltrials_gov":
        raise GovernanceError("Unsupported source governance profile")
    try:
        study = json.loads(text)
        protocol = study["protocolSection"]
        identification = protocol["identificationModule"]
        nct_id = str(identification["nctId"])
        official_title = str(identification.get("officialTitle") or identification["briefTitle"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise GovernanceError("ClinicalTrials.gov source is missing its authoritative identity") from exc
    if re.fullmatch(r"NCT[0-9]{8}", nct_id) is None or not official_title.strip():
        raise GovernanceError("ClinicalTrials.gov source has an invalid authoritative identity")
    module_names = (
        "identificationModule",
        "statusModule",
        "sponsorCollaboratorsModule",
        "conditionsModule",
        "designModule",
        "armsInterventionsModule",
        "outcomesModule",
        "eligibilityModule",
        "contactsLocationsModule",
    )
    profiled_protocol = {name: protocol[name] for name in module_names if name in protocol}
    contacts = profiled_protocol.get("contactsLocationsModule")
    if isinstance(contacts, dict):
        locations = contacts.get("locations")
        if isinstance(locations, list):
            contacts["locations"] = [
                {key: location[key] for key in ("facility", "city", "state", "country", "status") if key in location}
                for location in locations[:10]
                if isinstance(location, dict)
            ]
        contacts.pop("centralContacts", None)
        contacts.pop("overallOfficials", None)
    outcomes = profiled_protocol.get("outcomesModule")
    if isinstance(outcomes, dict):
        for field in ("primaryOutcomes", "secondaryOutcomes", "otherOutcomes"):
            if isinstance(outcomes.get(field), list):
                outcomes[field] = [
                    {
                        key: outcome[key]
                        for key in ("measure", "type", "timeFrame", "description", "unitOfMeasure")
                        if key in outcome
                    }
                    for outcome in outcomes[field][:10]
                    if isinstance(outcome, dict)
                ]
    arms = profiled_protocol.get("armsInterventionsModule")
    if isinstance(arms, dict):
        for field in ("armGroups", "interventions"):
            if isinstance(arms.get(field), list):
                arms[field] = arms[field][:50]
    sponsors = profiled_protocol.get("sponsorCollaboratorsModule")
    if isinstance(sponsors, dict):
        if isinstance(sponsors.get("collaborators"), list):
            sponsors["collaborators"] = [
                {key: collaborator[key] for key in ("name", "class") if key in collaborator}
                for collaborator in sponsors["collaborators"][:10]
                if isinstance(collaborator, dict)
            ]
        lead_sponsor = sponsors.get("leadSponsor")
        if isinstance(lead_sponsor, dict):
            sponsors["leadSponsor"] = {key: lead_sponsor[key] for key in ("name", "class") if key in lead_sponsor}
    eligibility = profiled_protocol.get("eligibilityModule")
    if isinstance(eligibility, dict):
        profiled_protocol["eligibilityModule"] = {
            key: eligibility[key]
            for key in (
                "healthyVolunteers",
                "sex",
                "minimumAge",
                "maximumAge",
                "stdAges",
                "genderBased",
                "samplingMethod",
            )
            if key in eligibility
        }
    profiled = _bound_profile_strings(
        {
            "protocolSection": profiled_protocol,
            "hasResults": bool(study.get("hasResults")),
        },
        max_string_chars,
    )
    return (
        json.dumps(profiled, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        {"registry_id": nct_id, "official_title": official_title},
    )


def _bound_profile_strings(value: Any, max_string_chars: int) -> Any:
    if isinstance(value, str):
        return value[:max_string_chars]
    if isinstance(value, list):
        return [_bound_profile_strings(item, max_string_chars) for item in value]
    if isinstance(value, dict):
        return {key: _bound_profile_strings(item, max_string_chars) for key, item in value.items()}
    return value


def _validate_profiled_response(
    envelope: ExtractionEnvelope,
    source_profile: str | None,
    identity: dict[str, str] | None,
) -> None:
    if source_profile is None:
        return
    if source_profile == "pubmed":
        if any(fact.fact_kind != "claim" for fact in envelope.facts):
            raise ModelGatewayError("PubMed governance may return only claim facts")
        return
    if source_profile != "clinicaltrials_gov" or identity is None:
        raise ModelGatewayError("Source governance profile identity is invalid")
    if len(envelope.facts) != 1 or not isinstance(envelope.facts[0], TrialFact):
        raise ModelGatewayError("ClinicalTrials.gov governance must return exactly one trial fact")
    fact = envelope.facts[0]
    if fact.registry_name.casefold() != "clinicaltrials.gov" or fact.registry_id != identity["registry_id"]:
        raise ModelGatewayError("ClinicalTrials.gov governance changed the authoritative registry identity")
    if fact.official_title != identity["official_title"]:
        raise ModelGatewayError("ClinicalTrials.gov governance changed the authoritative official title")
    if identity["registry_id"] not in fact.trial.external_ids.values():
        raise ModelGatewayError("ClinicalTrials.gov governance omitted the authoritative NCT identifier")


def _enforce_profiled_identity(
    envelope: ExtractionEnvelope,
    source_profile: str | None,
    identity: dict[str, str] | None,
) -> ExtractionEnvelope:
    if source_profile is None:
        return envelope
    if source_profile == "pubmed":
        return envelope
    if source_profile != "clinicaltrials_gov" or identity is None:
        raise ModelGatewayError("Source governance profile identity is invalid")
    if len(envelope.facts) != 1 or not isinstance(envelope.facts[0], TrialFact):
        return envelope
    fact = envelope.facts[0]
    authoritative_trial = fact.trial.model_copy(
        update={
            "name": identity["official_title"],
            "external_ids": {"NCT": identity["registry_id"]},
        }
    )
    authoritative_fact = fact.model_copy(
        update={
            "trial": authoritative_trial,
            "registry_name": "ClinicalTrials.gov",
            "registry_id": identity["registry_id"],
            "official_title": identity["official_title"],
        }
    )
    return envelope.model_copy(update={"facts": [authoritative_fact]})


def governance_policy_manifest(settings: Settings) -> dict[str, Any]:
    prompt = extraction_system_prompt(
        settings.ai_max_facts_per_segment,
        settings.ai_max_model_string_chars,
    )
    schema_parameters = (
        settings.ai_max_facts_per_segment,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
    )
    schemas = {
        "default_sha256": _hash_json(extraction_schema(*schema_parameters, allow_structure=False)),
        "structure_sha256": _hash_json(extraction_schema(*schema_parameters, allow_structure=True)),
    }
    clinicaltrials_fact_kinds = frozenset({"trial"})
    clinicaltrials_prompt = extraction_system_prompt(
        1,
        settings.ai_max_model_string_chars,
        fact_kind_allowlist=clinicaltrials_fact_kinds,
        source_profile="clinicaltrials_gov",
    )
    clinicaltrials_schema = extraction_schema(
        1,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
        fact_kind_allowlist=clinicaltrials_fact_kinds,
    )
    pubmed_fact_kinds = frozenset({"claim"})
    pubmed_max_facts = min(5, settings.ai_max_facts_per_segment)
    pubmed_prompt = extraction_system_prompt(
        pubmed_max_facts,
        settings.ai_max_model_string_chars,
        fact_kind_allowlist=pubmed_fact_kinds,
        source_profile="pubmed",
    )
    pubmed_schema = extraction_schema(
        pubmed_max_facts,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
        fact_kind_allowlist=pubmed_fact_kinds,
    )
    return {
        "schema": POLICY_SCHEMA,
        "governance_schema_name": SCHEMA_NAME,
        "governance_schema_version": SCHEMA_VERSION,
        "model_provider": "openai-compatible",
        "model_name": settings.ai_model,
        "model_endpoint_sha256": hashlib.sha256(settings.ai_base_url.strip().rstrip("/").encode("utf-8")).hexdigest(),
        "allowed_response_models": sorted(settings.ai_allowed_response_models),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_schemas": schemas,
        "source_profiles": {
            "clinicaltrials_gov": {
                "prompt_sha256": hashlib.sha256(clinicaltrials_prompt.encode("utf-8")).hexdigest(),
                "response_schema_sha256": _hash_json(clinicaltrials_schema),
                "max_facts": 1,
            },
            "pubmed": {
                "prompt_sha256": hashlib.sha256(pubmed_prompt.encode("utf-8")).hexdigest(),
                "response_schema_sha256": _hash_json(pubmed_schema),
                "max_facts": pubmed_max_facts,
            },
        },
        "limits": {
            "max_input_chars": settings.ai_max_input_chars,
            "max_document_chars": settings.ai_max_document_chars,
            "max_segments_per_document": settings.ai_max_segments_per_document,
            "max_facts_per_segment": settings.ai_max_facts_per_segment,
            "max_model_string_chars": settings.ai_max_model_string_chars,
            "max_model_collection_items": settings.ai_max_model_collection_items,
            "max_output_tokens_per_segment": settings.ai_max_output_tokens_per_segment,
            "max_document_input_tokens": settings.ai_max_document_input_tokens,
            "max_document_output_tokens": settings.ai_max_document_output_tokens,
            "max_response_bytes": settings.ai_max_response_bytes,
        },
        "accounting": {
            "require_usage_metadata": settings.ai_require_usage_metadata,
            "require_provider_request_id": settings.ai_require_provider_request_id,
            "input_cost_per_million_tokens": format(settings.ai_input_cost_per_million_tokens, "f"),
            "output_cost_per_million_tokens": format(settings.ai_output_cost_per_million_tokens, "f"),
            "max_document_cost": format(settings.ai_max_document_cost, "f"),
        },
        "publication": {
            "auto_publish_threshold": format(Decimal(str(settings.ai_auto_publish_threshold)), "f"),
            "auto_publish_fact_kinds": sorted(settings.ai_auto_publish_fact_kinds),
            "high_risk_fact_kinds": sorted(HIGH_RISK_FACT_KINDS),
        },
    }


def governance_policy_sha256(settings: Settings) -> str:
    return _hash_json(governance_policy_manifest(settings))


def _hash_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prepared_fact_key(prepared: PreparedFact) -> str:
    if isinstance(prepared.fact, StructureFact):
        inchi_key = prepared.payload.get("standard_inchi_key")
        if isinstance(inchi_key, str) and inchi_key:
            return _hash_identity({"kind": "structure", "standard_inchi_key": inchi_key})
    return _fact_key(prepared.fact)


def _fact_key(fact: ExtractedFact) -> str:
    return _hash_identity(_fact_identity(fact))


def _hash_identity(identity: dict[str, Any]) -> str:
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fact_identity(fact: ExtractedFact) -> dict[str, Any]:
    if isinstance(fact, ClaimFact):
        return {
            "kind": fact.fact_kind,
            "subject": _entity_identity(fact.subject.model_dump(mode="json")),
            "predicate": fact.predicate,
            "qualifier_keys": sorted(fact.qualifiers),
        }
    if isinstance(fact, TargetProfileFact):
        return {"kind": fact.fact_kind, "subject": _entity_identity(fact.subject.model_dump(mode="json"))}
    if isinstance(fact, TargetEvidenceFact):
        return {
            "kind": fact.fact_kind,
            "record_identifier": fact.record_identifier.casefold(),
            "target": _entity_identity(fact.target.model_dump(mode="json")),
        }
    if isinstance(fact, StructureFact):
        return {
            "kind": fact.fact_kind,
            "subject": _entity_identity(fact.subject.model_dump(mode="json")),
            "reported_smiles": fact.canonical_smiles.strip(),
        }
    if isinstance(fact, ActivityFact):
        return {
            "kind": fact.fact_kind,
            "compound": _entity_identity(fact.compound.model_dump(mode="json")),
            "target": _entity_identity(fact.target.model_dump(mode="json")),
            "assay_name": fact.assay_name.casefold(),
            "reported_type": fact.reported_type.casefold(),
        }
    if isinstance(fact, ProgramFact):
        program_payload = fact.model_dump(mode="json")
        targets = list(program_payload.get("targets") or [])
        if program_payload.get("target") is not None:
            targets = [
                {
                    "role": ProgramTargetRole.PRIMARY.value,
                    "entity": program_payload["target"],
                }
            ]
        organizations = list(program_payload.get("organizations") or [])
        if program_payload.get("organization") is not None and not organizations:
            organizations = [
                {
                    "role": "originator",
                    "entity": program_payload["organization"],
                }
            ]
        return {
            "kind": fact.fact_kind,
            "drug": _entity_identity(fact.drug.model_dump(mode="json")),
            "targets": [
                {
                    "role": str(item["role"]),
                    "entity": _entity_identity(item["entity"]),
                }
                for item in targets
            ],
            "indication": _entity_identity(fact.indication.model_dump(mode="json")) if fact.indication else None,
            "organizations": [
                {
                    "role": str(item["role"]),
                    "entity": _entity_identity(item["entity"]),
                }
                for item in organizations
            ],
        }
    if isinstance(fact, TrialFact):
        return {"kind": fact.fact_kind, "registry": fact.registry_name.casefold(), "id": fact.registry_id.casefold()}
    if isinstance(fact, PatentFact):
        return {"kind": fact.fact_kind, "family": fact.family_identifier.casefold()}
    if isinstance(fact, DealFact):
        return {"kind": fact.fact_kind, "deal": _entity_identity(fact.deal.model_dump(mode="json"))}
    if isinstance(fact, RegulatoryFact):
        return {
            "kind": fact.fact_kind,
            "agency": fact.agency.casefold(),
            "event_identifier": fact.event_identifier.casefold(),
        }
    if isinstance(fact, EpidemiologyFact):
        return {
            "kind": fact.fact_kind,
            "observation_identifier": fact.observation_identifier.casefold(),
            "disease": _entity_identity(fact.disease.model_dump(mode="json")),
        }
    if isinstance(fact, NewsFact):
        return {"kind": fact.fact_kind, "event_identifier": fact.event_identifier.casefold()}
    raise TypeError(f"Unsupported fact type: {type(fact).__name__}")


def _entity_identity(reference: dict[str, Any]) -> dict[str, Any]:
    external_ids = reference.get("external_ids") or {}
    return {
        "entity_type": str(reference["entity_type"]),
        "name": " ".join(str(reference["name"]).casefold().split()),
        "external_ids": dict(sorted(external_ids.items())),
    }


def _reference_matches_entity(reference: object, entity: Entity) -> bool:
    if not isinstance(reference, dict):
        return False
    if str(reference.get("entity_type")) != entity.entity_type.value:
        return False
    name = " ".join(str(reference.get("name") or "").casefold().split())
    if name and name == entity.normalized_name:
        return True
    supplied_ids = reference.get("external_ids")
    if not isinstance(supplied_ids, dict):
        return False
    return any(entity.external_ids.get(str(key)) == str(value) for key, value in supplied_ids.items())


def _authority_value_matches(current: object, expected: str | float) -> bool:
    if isinstance(expected, float):
        return (
            isinstance(current, int | float)
            and not isinstance(current, bool)
            and abs(float(current) - expected) <= 1e-6
        )
    return current == expected


def _primary_subject(payload: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "subject",
        "compound",
        "drug",
        "trial",
        "patent",
        "deal",
        "disease",
        "publisher",
    ):
        value = payload.get(key)
        if isinstance(value, dict):
            return cast(dict[str, Any], value)
    raise GovernanceError("Extracted fact does not have a primary subject")


def _payload_without_citation(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "citation"}


def _projection(resource_type: str, resource_id: str) -> dict[str, str]:
    return {"resource_type": resource_type, "resource_id": resource_id}


def _normalize_phase(value: str) -> DevelopmentPhase | None:
    chinese_value = re.sub(r"\s+", "", value).casefold()
    chinese_aliases = {
        "药物发现": DevelopmentPhase.DISCOVERY,
        "发现": DevelopmentPhase.DISCOVERY,
        "临床前": DevelopmentPhase.PRECLINICAL,
        "临床前研究": DevelopmentPhase.PRECLINICAL,
        "申报临床": DevelopmentPhase.IND,
        "临床申请": DevelopmentPhase.IND,
        "i期临床": DevelopmentPhase.PHASE_1,
        "ⅰ期临床": DevelopmentPhase.PHASE_1,
        "一期临床": DevelopmentPhase.PHASE_1,
        "i/ii期临床": DevelopmentPhase.PHASE_1_2,
        "i-ii期临床": DevelopmentPhase.PHASE_1_2,
        "ⅰ/ⅱ期临床": DevelopmentPhase.PHASE_1_2,
        "一期/二期临床": DevelopmentPhase.PHASE_1_2,
        "ii期临床": DevelopmentPhase.PHASE_2,
        "ⅱ期临床": DevelopmentPhase.PHASE_2,
        "二期临床": DevelopmentPhase.PHASE_2,
        "ii/iii期临床": DevelopmentPhase.PHASE_2_3,
        "ii-iii期临床": DevelopmentPhase.PHASE_2_3,
        "ⅱ/ⅲ期临床": DevelopmentPhase.PHASE_2_3,
        "二期/三期临床": DevelopmentPhase.PHASE_2_3,
        "iii期临床": DevelopmentPhase.PHASE_3,
        "ⅲ期临床": DevelopmentPhase.PHASE_3,
        "三期临床": DevelopmentPhase.PHASE_3,
        "申请上市": DevelopmentPhase.FILED,
        "申报上市": DevelopmentPhase.FILED,
        "上市申请": DevelopmentPhase.FILED,
        "批准上市": DevelopmentPhase.APPROVED,
        "已批准": DevelopmentPhase.APPROVED,
        "已上市": DevelopmentPhase.APPROVED,
        "停止": DevelopmentPhase.DISCONTINUED,
        "停止研发": DevelopmentPhase.DISCONTINUED,
        "终止": DevelopmentPhase.DISCONTINUED,
        "撤回": DevelopmentPhase.DISCONTINUED,
    }
    if chinese_value in chinese_aliases:
        return chinese_aliases[chinese_value]
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    aliases = {
        "discovery": DevelopmentPhase.DISCOVERY,
        "research": DevelopmentPhase.DISCOVERY,
        "preclinical": DevelopmentPhase.PRECLINICAL,
        "pre_clinical": DevelopmentPhase.PRECLINICAL,
        "ind": DevelopmentPhase.IND,
        "phase_1": DevelopmentPhase.PHASE_1,
        "phase_i": DevelopmentPhase.PHASE_1,
        "phase_1_2": DevelopmentPhase.PHASE_1_2,
        "phase_i_ii": DevelopmentPhase.PHASE_1_2,
        "phase_2": DevelopmentPhase.PHASE_2,
        "phase_ii": DevelopmentPhase.PHASE_2,
        "phase_2_3": DevelopmentPhase.PHASE_2_3,
        "phase_ii_iii": DevelopmentPhase.PHASE_2_3,
        "phase_3": DevelopmentPhase.PHASE_3,
        "phase_iii": DevelopmentPhase.PHASE_3,
        "filed": DevelopmentPhase.FILED,
        "registration": DevelopmentPhase.FILED,
        "nda_bla_filed": DevelopmentPhase.FILED,
        "approved": DevelopmentPhase.APPROVED,
        "marketed": DevelopmentPhase.APPROVED,
        "discontinued": DevelopmentPhase.DISCONTINUED,
        "terminated": DevelopmentPhase.DISCONTINUED,
        "withdrawn": DevelopmentPhase.DISCONTINUED,
    }
    return aliases.get(normalized)
