from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.enterprise.llm_providers import effective_ai_settings
from pharma_intel.governance.adapter_chembl import govern_chembl
from pharma_intel.governance.adapter_clinicaltrials import govern_clinicaltrials_gov
from pharma_intel.governance.adapter_nextpharma import govern_nextpharma
from pharma_intel.governance.chembl import (
    ADAPTER_NAME as CHEMBL_ADAPTER_NAME,
)
from pharma_intel.governance.citations import (
    _deduplicate_prepared_facts,
    _quote_source_match,
    _segments,
)
from pharma_intel.governance.clinicaltrials_gov import (
    ADAPTER_NAME as CLINICALTRIALS_GOV_ADAPTER_NAME,
)
from pharma_intel.governance.contracts import (
    CLINICALTRIALS_PROFILE_INPUT_STRING_CHARS as CLINICALTRIALS_PROFILE_INPUT_STRING_CHARS,
)
from pharma_intel.governance.contracts import (
    HIGH_RISK_FACT_KINDS as HIGH_RISK_FACT_KINDS,
)
from pharma_intel.governance.contracts import (
    MILLION_TOKENS as MILLION_TOKENS,
)
from pharma_intel.governance.contracts import (
    POLICY_SCHEMA as POLICY_SCHEMA,
)
from pharma_intel.governance.contracts import (
    SCHEMA_NAME as SCHEMA_NAME,
)
from pharma_intel.governance.contracts import (
    SCHEMA_VERSION as SCHEMA_VERSION,
)
from pharma_intel.governance.contracts import (
    DocumentSegment as DocumentSegment,
)
from pharma_intel.governance.contracts import (
    GovernanceBudgetError as GovernanceBudgetError,
)
from pharma_intel.governance.contracts import (
    GovernanceError as GovernanceError,
)
from pharma_intel.governance.contracts import (
    PreparedSegmentFact as PreparedSegmentFact,
)
from pharma_intel.governance.contracts import (
    SourceQuoteMatch as SourceQuoteMatch,
)
from pharma_intel.governance.fact_identity import (
    _payload_without_citation,
    _prepared_fact_key,
    _primary_subject,
    _reference_matches_entity,
)
from pharma_intel.governance.materialization import materialize_structured_fact
from pharma_intel.governance.model_audit import (
    _extraction_audit,
    _model_cost,
)
from pharma_intel.governance.model_gateway import (
    ModelGatewayError,
    OpenAICompatibleExtractionGateway,
    extraction_system_prompt,
)
from pharma_intel.governance.nextpharma import (
    ADAPTER_NAME as NEXTPHARMA_ADAPTER_NAME,
)
from pharma_intel.governance.normalization import FactNormalizer, PreparedFact
from pharma_intel.governance.policy import (
    governance_policy_manifest as governance_policy_manifest,
)
from pharma_intel.governance.policy import (
    governance_policy_sha256 as governance_policy_sha256,
)
from pharma_intel.governance.schemas import (
    ExtractionEnvelope,
    ProgramFact,
    StructureFact,
    TargetProfileFact,
    TrialFact,
)
from pharma_intel.governance.source_policy import source_profile as resolve_source_profile
from pharma_intel.governance.source_profiles import (
    _enforce_profiled_identity,
    _profiled_model_text,
    _validate_profiled_response,
)
from pharma_intel.governance.source_updates import (
    OfficialSourceUpdate,
    lock_official_source_record,
    official_source_update,
)
from pharma_intel.identity import EntityIdentityService, IdentityError
from pharma_intel.models import (
    CompoundStructure,
    DataSource,
    DataSourceType,
    Entity,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    OutboxEvent,
    Relationship,
    ReviewStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
)
from pharma_intel.object_store import ObjectStore


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
        source_profile = resolve_source_profile(self.session, version)
        if source_profile == NEXTPHARMA_ADAPTER_NAME:
            return govern_nextpharma(self, version)
        if source_profile == CHEMBL_ADAPTER_NAME:
            return govern_chembl(self, version)
        if source_profile == CLINICALTRIALS_GOV_ADAPTER_NAME:
            return govern_clinicaltrials_gov(self, version)
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
        if trusted_structured:
            lock_official_source_record(self.session, version)
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
                select(StagedFact)
                .execution_options(populate_existing=True)
                .where(
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
        official_update = (
            official_source_update(self.session, version, prior)
            if trusted_structured and fact.citation.confidence == 1
            else OfficialSourceUpdate()
        )
        superseded_prior = (
            [item for item in prior if item.status in {GovernanceStatus.REVIEW_PENDING, GovernanceStatus.CONFLICT}]
            if authoritative_trial
            else []
        )
        superseded_prior.extend(
            item for item in prior if item.id in official_update.superseded_ids and item not in superseded_prior
        )
        superseded_ids = {item.id for item in superseded_prior}
        conflicts = [
            item.id
            for item in prior
            if item.id not in superseded_ids
            and _payload_without_citation(item.payload) != _payload_without_citation(payload)
        ]
        if official_update.stale:
            quality_findings.append(
                {
                    "code": "stale_official_source_version",
                    "severity": "error",
                    "message": "A newer deterministic revision of this source record is already accepted",
                }
            )
            conflicts = []
        if conflicts:
            quality_findings.append(
                {"code": "conflicting_fact", "severity": "warning", "message": "A prior fact has different values"}
            )

        canonical_conflict = self._structure_entity_conflict(prepared, quality_findings)

        if prepared.hard_reject or not segment_fact.quote_verified or official_update.stale:
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
        if superseded_prior and status == GovernanceStatus.VALIDATED:
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
            task.decision_notes = "Superseded by a validated authoritative source revision"
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
        projections = materialize_structured_fact(self, staged, payload)
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
