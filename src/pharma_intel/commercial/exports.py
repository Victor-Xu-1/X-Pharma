from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from pharma_intel.commercial.cursor import SignedCursorCodec, query_fingerprint
from pharma_intel.commercial.service import (
    CommercialAccessDenied,
    CommercialError,
    CommercialNotConfigured,
    CommercialUsageService,
    IdempotencyConflict,
    ReserveCommand,
    SettleCommand,
)
from pharma_intel.config import Settings
from pharma_intel.licensing import (
    ExportFieldPolicy,
    canonical_policy_sha256,
    full_export_field_policy,
)
from pharma_intel.models import (
    ActivityMeasurement,
    AgentClient,
    AgentClientSubject,
    AuditEvent,
    BillingAccount,
    BillingAccountStatus,
    ClinicalTrialProfile,
    CommercialExportPolicy,
    CommercialSubscription,
    CompoundStructure,
    DataExportJob,
    DealProfile,
    DevelopmentProgram,
    Entity,
    FactProvenanceLink,
    OutboxEvent,
    PatentFamily,
    RegulatoryEvent,
    SubscriptionStatus,
    new_uuid,
)
from pharma_intel.object_store import ObjectStore, build_object_store
from pharma_intel.security import Principal

EXPORT_BILLING_CLASS = "export.data"
ACTIVE_EXPORT_STATES = ("pending_approval", "queued", "running", "completed")


class ExportValidationError(CommercialError):
    pass


class ExportNotFound(CommercialAccessDenied):
    pass


class ExportStateConflict(CommercialError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    model: type[Any]
    fields: tuple[str, ...]
    filter_fields: tuple[str, ...]


DATASETS: dict[str, DatasetSpec] = {
    "entities": DatasetSpec(
        Entity,
        (
            "id",
            "entity_type",
            "name",
            "normalized_name",
            "description",
            "external_ids",
            "attributes",
            "review_status",
            "created_at",
            "updated_at",
        ),
        ("id", "entity_type", "normalized_name", "review_status", "created_at", "updated_at"),
    ),
    "structures": DatasetSpec(
        CompoundStructure,
        (
            "id",
            "entity_id",
            "canonical_smiles",
            "isomeric_smiles",
            "standard_inchi",
            "standard_inchi_key",
            "molecular_formula",
            "molecular_weight",
            "exact_mass",
            "structure_version",
            "standardization_version",
            "fingerprint_version",
            "created_at",
            "updated_at",
        ),
        ("id", "entity_id", "standard_inchi_key", "molecular_formula", "created_at", "updated_at"),
    ),
    "bioactivities": DatasetSpec(
        ActivityMeasurement,
        (
            "id",
            "source_system",
            "source_activity_id",
            "assay_id",
            "compound_entity_id",
            "target_entity_id",
            "reported_type",
            "reported_relation",
            "reported_value",
            "reported_units",
            "standard_type",
            "standard_relation",
            "standard_value",
            "standard_units",
            "pchembl_value",
            "qualifiers",
            "validity_comment",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "source_system",
            "assay_id",
            "compound_entity_id",
            "target_entity_id",
            "standard_type",
            "standard_value",
            "pchembl_value",
            "created_at",
            "updated_at",
        ),
    ),
    "competitive_programs": DatasetSpec(
        DevelopmentProgram,
        (
            "id",
            "drug_entity_id",
            "target_entity_id",
            "disease_entity_id",
            "organization_entity_id",
            "modality",
            "mechanism_of_action",
            "phase",
            "status_date",
            "geography",
            "status_detail",
            "source_document_id",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "drug_entity_id",
            "target_entity_id",
            "disease_entity_id",
            "organization_entity_id",
            "modality",
            "phase",
            "status_date",
            "geography",
            "created_at",
            "updated_at",
        ),
    ),
    "clinical_trials": DatasetSpec(
        ClinicalTrialProfile,
        (
            "id",
            "entity_id",
            "registry_name",
            "registry_id",
            "official_title",
            "overall_status",
            "phases",
            "study_type",
            "enrollment",
            "start_date",
            "completion_date",
            "interventions",
            "conditions",
            "sponsors",
            "outcomes",
            "locations",
            "last_update_posted",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "entity_id",
            "registry_name",
            "registry_id",
            "overall_status",
            "study_type",
            "enrollment",
            "start_date",
            "completion_date",
            "last_update_posted",
            "created_at",
            "updated_at",
        ),
    ),
    "patents": DatasetSpec(
        PatentFamily,
        (
            "id",
            "entity_id",
            "family_identifier",
            "title",
            "priority_date",
            "applicants",
            "inventors",
            "publications",
            "legal_status",
            "expiration_date",
            "linked_entity_ids",
            "source_document_id",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "entity_id",
            "family_identifier",
            "priority_date",
            "legal_status",
            "expiration_date",
            "created_at",
            "updated_at",
        ),
    ),
    "deals": DatasetSpec(
        DealProfile,
        (
            "id",
            "entity_id",
            "deal_type",
            "announced_at",
            "parties",
            "asset_entity_ids",
            "territory",
            "upfront_amount",
            "total_potential_amount",
            "currency",
            "terms",
            "source_document_id",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "entity_id",
            "deal_type",
            "announced_at",
            "currency",
            "created_at",
            "updated_at",
        ),
    ),
    "regulatory_events": DatasetSpec(
        RegulatoryEvent,
        (
            "id",
            "subject_entity_id",
            "agency",
            "jurisdiction",
            "event_identifier",
            "application_number",
            "event_type",
            "status",
            "title",
            "decision_date",
            "indication_entity_id",
            "organization_entity_id",
            "details",
            "source_document_id",
            "created_at",
            "updated_at",
        ),
        (
            "id",
            "subject_entity_id",
            "agency",
            "jurisdiction",
            "event_identifier",
            "application_number",
            "event_type",
            "status",
            "decision_date",
            "indication_entity_id",
            "organization_entity_id",
            "created_at",
            "updated_at",
        ),
    ),
    "fact_provenance": DatasetSpec(
        FactProvenanceLink,
        (
            "id",
            "resource_type",
            "resource_id",
            "staged_fact_id",
            "evidence_claim_id",
            "source_asset_id",
            "source_version_id",
            "source_document_id",
            "dataset_key",
            "source_locator",
            "created_at",
        ),
        (
            "id",
            "resource_type",
            "resource_id",
            "evidence_claim_id",
            "source_asset_id",
            "source_version_id",
            "source_document_id",
            "dataset_key",
            "created_at",
        ),
    ),
}


class ExportPolicyConfigurationError(ValueError):
    pass


def default_export_field_policy(
    *,
    policy_version: str = "tenant-owned-v1",
    attribution: str = "Tenant-owned authoritative data",
) -> dict[str, Any]:
    return full_export_field_policy(
        {key: (spec.fields, spec.filter_fields) for key, spec in DATASETS.items()},
        policy_version=policy_version,
        attribution=attribution,
    )


def validate_export_field_policy(value: dict[str, Any]) -> ExportFieldPolicy:
    try:
        policy = ExportFieldPolicy.model_validate(value)
    except ValidationError as exc:
        raise ExportPolicyConfigurationError("Export field policy is invalid") from exc
    unknown_datasets = set(policy.datasets) - set(DATASETS)
    if unknown_datasets:
        raise ExportPolicyConfigurationError("Export field policy contains unsupported datasets")
    for dataset, dataset_policy in policy.datasets.items():
        spec = DATASETS[dataset]
        if set(dataset_policy.fields) - set(spec.fields):
            raise ExportPolicyConfigurationError(f"Export field policy contains unsupported {dataset} fields")
        if set(dataset_policy.filter_fields) - set(spec.filter_fields):
            raise ExportPolicyConfigurationError(f"Export field policy contains unsupported {dataset} filters")
    return policy


@dataclass(frozen=True)
class CreateExportCommand:
    dataset: str
    export_format: str
    filters: dict[str, Any]
    fields: list[str]
    max_records: int
    max_billable_units: Decimal | str
    idempotency_key: str


@dataclass(frozen=True)
class ExportChunk:
    items: list[dict[str, Any]]
    count: int
    next_cursor: str | None
    manifest: dict[str, Any]


@dataclass(frozen=True)
class SignedExportManifest:
    payload: dict[str, Any]
    sha256: str
    key_id: str
    signature: str

    def envelope(self) -> dict[str, Any]:
        return {
            "schema": "pharma.data-export-envelope.v1",
            "payload": self.payload,
            "sha256": self.sha256,
            "signature": {
                "algorithm": "HMAC-SHA256",
                "key_id": self.key_id,
                "value": self.signature,
            },
        }


class ExportManifestSigner:
    def __init__(self, secret: str, *, key_id: str) -> None:
        secret_bytes = secret.encode("utf-8")
        if len(secret_bytes) < 32:
            raise ValueError("Export manifest signing secret must contain at least 32 bytes")
        if not key_id or len(key_id) > 120:
            raise ValueError("Export manifest signing key ID is invalid")
        self._secret = secret_bytes
        self.key_id = key_id

    def sign(self, payload: dict[str, Any]) -> SignedExportManifest:
        body = _canonical_bytes(payload)
        return SignedExportManifest(
            payload=payload,
            sha256=hashlib.sha256(body).hexdigest(),
            key_id=self.key_id,
            signature=hmac.new(self._secret, body, hashlib.sha256).hexdigest(),
        )

    def verify(self, manifest: SignedExportManifest) -> bool:
        expected = self.sign(manifest.payload)
        return (
            manifest.key_id == self.key_id
            and hmac.compare_digest(manifest.sha256, expected.sha256)
            and hmac.compare_digest(manifest.signature, expected.signature)
        )


class CommercialExportService:
    def __init__(
        self,
        session: Session,
        object_store: ObjectStore,
        manifest_signer: ExportManifestSigner,
        cursor_codec: SignedCursorCodec,
        *,
        export_reservation_lease_seconds: int = 7200,
        max_durable_result_bytes: int = 2_000_000,
        max_billable_units_per_call: Decimal | str = Decimal("1000000"),
        max_active_reservations_per_client: int = 20,
        read_page_size_max: int = 250,
    ) -> None:
        self.session = session
        self.object_store = object_store
        self.manifest_signer = manifest_signer
        self.cursor_codec = cursor_codec
        self.export_reservation_lease_seconds = export_reservation_lease_seconds
        self.max_durable_result_bytes = max_durable_result_bytes
        self.max_billable_units_per_call = max_billable_units_per_call
        self.max_active_reservations_per_client = max_active_reservations_per_client
        self.read_page_size_max = read_page_size_max

    def create(self, principal: Principal, command: CreateExportCommand) -> DataExportJob:
        principal.require("data:export")
        timestamp = datetime.now(UTC)
        client, subscription = self._bound_access(principal, timestamp)
        policy = self._policy(principal.tenant_id, subscription.billing_account_id, lock=True)
        field_policy = self._field_policy(policy)
        field_policy_document = field_policy.document()
        field_policy_sha256 = canonical_policy_sha256(field_policy_document)
        normalized_fields = self._validate_request(policy, field_policy, command)
        request_payload = {
            "dataset": command.dataset,
            "license_policy_version": field_policy.policy_version,
            "license_policy_sha256": field_policy_sha256,
            "export_format": command.export_format,
            "filters": command.filters,
            "fields": normalized_fields,
            "max_records": command.max_records,
            "max_billable_units": str(command.max_billable_units),
        }
        request_sha256 = hashlib.sha256(_canonical_bytes(request_payload)).hexdigest()
        existing = self.session.scalar(
            select(DataExportJob).where(
                DataExportJob.tenant_id == principal.tenant_id,
                DataExportJob.agent_client_id == client.id,
                DataExportJob.idempotency_key == command.idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_sha256 != request_sha256:
                raise IdempotencyConflict("Idempotency key was already used for a different export")
            return self._repair_reservation(existing, principal)

        day_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        allocated = int(
            self.session.scalar(
                select(func.coalesce(func.sum(DataExportJob.max_records), 0)).where(
                    DataExportJob.tenant_id == principal.tenant_id,
                    DataExportJob.billing_account_id == subscription.billing_account_id,
                    DataExportJob.requested_at >= day_start,
                    DataExportJob.state.in_(ACTIVE_EXPORT_STATES),
                )
            )
            or 0
        )
        if allocated + command.max_records > policy.daily_record_limit:
            raise CommercialAccessDenied("Customer-level daily export allocation would be exceeded")

        approval_required = command.max_records > policy.approval_required_above
        job_id = new_uuid()
        job = DataExportJob(
            id=job_id,
            tenant_id=principal.tenant_id,
            billing_account_id=subscription.billing_account_id,
            subscription_id=subscription.id,
            agent_client_id=client.id,
            actor_type=principal.actor_type,
            subject_id=principal.actor_id,
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha256,
            dataset=command.dataset,
            license_policy_version=field_policy.policy_version,
            license_policy_sha256=field_policy_sha256,
            license_attribution=field_policy.attribution,
            export_format=command.export_format,
            filters_json=command.filters,
            fields_json=normalized_fields,
            max_records=command.max_records,
            max_billable_units=Decimal(str(command.max_billable_units)),
            state="pending_approval",
            approval_required=approval_required,
            workflow_id=f"data-export-{job_id}",
            requested_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.session.add(job)
        self._audit(job, principal.actor_type, principal.actor_id, "commercial.export.request", "success")
        self.session.commit()
        if approval_required:
            return job
        return self._reserve_job(job, principal)

    def approve(self, principal: Principal, job_id: str) -> DataExportJob:
        principal.require("commercial:write")
        job = self._job_for_tenant(principal.tenant_id, job_id, lock=True)
        if job.state == "queued" and job.reservation_id:
            return job
        if job.state != "pending_approval" or not job.approval_required:
            raise ExportStateConflict("Export job is not awaiting approval")
        client = self.session.get(AgentClient, job.agent_client_id)
        if client is None or not client.active:
            raise CommercialNotConfigured("Export Agent client is inactive")
        agent_principal = Principal(
            tenant_id=job.tenant_id,
            actor_id=job.subject_id,
            actor_type=job.actor_type,  # type: ignore[arg-type]
            scopes=frozenset({"data:export"}),
            client_id=client.oauth_client_id,
        )
        reserved = self._reserve_job(job, agent_principal)
        reserved.approved_by = principal.actor_id
        reserved.approved_at = datetime.now(UTC)
        reserved.updated_at = datetime.now(UTC)
        self._audit(reserved, "user", principal.actor_id, "commercial.export.approve", "success")
        self.session.commit()
        return reserved

    def cancel(self, principal: Principal, job_id: str) -> DataExportJob:
        principal.require("data:export")
        job = self._owned_job(principal, job_id, lock=True)
        return self._cancel_locked(job, principal)

    def cancel_as_operator(self, principal: Principal, job_id: str) -> DataExportJob:
        principal.require("commercial:write")
        job = self._job_for_tenant(principal.tenant_id, job_id, lock=True)
        client = self.session.get(AgentClient, job.agent_client_id)
        if client is None:
            raise CommercialNotConfigured("Export Agent client is unavailable")
        agent_principal = Principal(
            tenant_id=job.tenant_id,
            actor_id=job.subject_id,
            actor_type=job.actor_type,  # type: ignore[arg-type]
            scopes=frozenset({"data:export"}),
            client_id=client.oauth_client_id,
        )
        result = self._cancel_locked(job, agent_principal)
        self._audit(result, "user", principal.actor_id, "commercial.export.cancel", "success")
        self.session.commit()
        return result

    def get(self, principal: Principal, job_id: str) -> DataExportJob:
        principal.require("data:export")
        return self._owned_job(principal, job_id, lock=False)

    def list_for_operator(self, principal: Principal, *, limit: int = 100) -> list[DataExportJob]:
        principal.require("commercial:read")
        if not 1 <= limit <= 500:
            raise ExportValidationError("Export list limit must be between 1 and 500")
        return list(
            self.session.scalars(
                select(DataExportJob)
                .where(DataExportJob.tenant_id == principal.tenant_id)
                .order_by(DataExportJob.created_at.desc())
                .limit(limit)
            )
        )

    def execute(self, tenant_id: str, job_id: str) -> DataExportJob:
        job = self._job_for_tenant(tenant_id, job_id, lock=True)
        if job.state == "completed":
            return job
        if job.state == "cancel_requested":
            return self._cancel_worker_job(job)
        if job.state not in {"queued", "running"} or not job.reservation_id:
            raise ExportStateConflict("Export job is not executable")
        policy = self._policy(job.tenant_id, job.billing_account_id, lock=False)
        self._assert_license_policy_current(job, policy)
        principal = self._job_principal(job)
        usage = self._usage_service(principal)
        usage.authorize_paginated_query(
            job.reservation_id,
            billing_class=EXPORT_BILLING_CLASS,
            request_arguments=self._reservation_arguments(job),
            page_size=job.max_records,
        )
        if job.state == "queued":
            job.state = "running"
            job.started_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            self.session.commit()

        records = self._query_records(job)
        artifact = self._encode_records(job.export_format, job.fields_json, records)
        if len(artifact) > policy.max_artifact_bytes:
            raise ExportValidationError("Export artifact exceeds the customer policy size limit")
        artifact_sha256 = hashlib.sha256(artifact).hexdigest()
        stored_artifact = self.object_store.put_bytes(
            job.tenant_id,
            f"exports-{job.id}",
            artifact,
            artifact_sha256,
            f".{job.export_format}",
        )
        completed_at = datetime.now(UTC)
        expires_at = completed_at + timedelta(seconds=policy.artifact_ttl_seconds)
        manifest_payload = {
            "schema": "pharma.data-export-manifest.v1",
            "job_id": job.id,
            "tenant_id": job.tenant_id,
            "dataset": job.dataset,
            "format": job.export_format,
            "fields": job.fields_json,
            "filter_sha256": hashlib.sha256(_canonical_bytes(job.filters_json)).hexdigest(),
            "record_count": len(records),
            "artifact_bytes": stored_artifact.size_bytes,
            "artifact_sha256": stored_artifact.content_sha256,
            "as_of": completed_at.isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "authority": "PostgreSQL tenant authority store",
            "license": {
                "policy_version": job.license_policy_version,
                "policy_sha256": job.license_policy_sha256,
                "attribution": job.license_attribution,
            },
        }
        signed_manifest = self.manifest_signer.sign(manifest_payload)
        manifest_bytes = _canonical_bytes(signed_manifest.envelope())
        stored_manifest = self.object_store.put_bytes(
            job.tenant_id,
            f"export-manifests-{job.id}",
            manifest_bytes,
            hashlib.sha256(manifest_bytes).hexdigest(),
            ".json",
        )
        usage.settle(
            SettleCommand(
                reservation_id=job.reservation_id,
                result_count=len(records),
                result={
                    "items": [{"id": record["id"]} for record in records],
                    "export_manifest": signed_manifest.envelope(),
                },
                metrics={
                    "compute_units": "0",
                    "delivered_bytes": stored_artifact.size_bytes,
                    "export_job_id": job.id,
                },
                request_id=new_uuid(),
            )
        )
        job = self._job_for_tenant(tenant_id, job_id, lock=True)
        job.state = "completed"
        job.record_count = len(records)
        job.artifact_uri = stored_artifact.uri
        job.artifact_sha256 = stored_artifact.content_sha256
        job.artifact_bytes = stored_artifact.size_bytes
        job.manifest_uri = stored_manifest.uri
        job.manifest_sha256 = stored_manifest.content_sha256
        job.manifest_signature = signed_manifest.signature
        job.manifest_key_id = signed_manifest.key_id
        job.completed_at = completed_at
        job.expires_at = expires_at
        job.updated_at = completed_at
        self._audit(job, "system", "temporal-export-worker", "commercial.export.complete", "success")
        self._outbox(job, "commercial.export_completed.v1")
        self.session.commit()
        return job

    def fail(self, tenant_id: str, job_id: str, *, code: str, message: str) -> DataExportJob:
        job = self._job_for_tenant(tenant_id, job_id, lock=True)
        if job.state in {"completed", "cancelled", "failed"}:
            return job
        if job.reservation_id:
            usage = self._usage_service(self._job_principal(job))
            usage.release(job.reservation_id, reason=message[:500], request_id=new_uuid())
            job = self._job_for_tenant(tenant_id, job_id, lock=True)
        job.state = "failed"
        job.failure_code = code[:120]
        job.failure_message = message[:500]
        job.completed_at = datetime.now(UTC)
        job.updated_at = job.completed_at
        self._audit(job, "system", "temporal-export-worker", "commercial.export.fail", "failure")
        self._outbox(job, "commercial.export_failed.v1")
        self.session.commit()
        return job

    def read_chunk(
        self,
        principal: Principal,
        job_id: str,
        *,
        limit: int,
        cursor: str | None,
    ) -> ExportChunk:
        principal.require("data:export")
        if not 1 <= limit <= self.read_page_size_max:
            raise ExportValidationError(f"Export chunk limit must be between 1 and {self.read_page_size_max}")
        job = self._owned_job(principal, job_id, lock=False)
        now = datetime.now(UTC)
        if job.state != "completed" or not job.artifact_uri or not job.manifest_uri:
            raise ExportStateConflict("Export artifact is not available")
        if job.expires_at is None or _as_utc(job.expires_at) <= now:
            raise ExportStateConflict("Export artifact has expired")
        query_sha256 = query_fingerprint("export.read", {"job_id": job.id}, limit)
        offset = 0
        depth = 1
        chain_id: str | None = None
        if cursor:
            claims = self.cursor_codec.verify(
                cursor,
                principal,
                tool="export.read",
                query_sha256=query_sha256,
                page_size=limit,
            )
            offset = claims.offset
            depth = claims.depth
            chain_id = claims.chain_id
        policy = self._policy(job.tenant_id, job.billing_account_id, lock=False)
        self._assert_license_policy_current(job, policy)
        artifact = self.object_store.read_bytes(job.artifact_uri, policy.max_artifact_bytes)
        if hashlib.sha256(artifact).hexdigest() != job.artifact_sha256:
            raise ExportStateConflict("Export artifact checksum verification failed")
        records = self._decode_records(job.export_format, artifact)
        items = records[offset : offset + limit]
        next_offset = offset + len(items)
        next_cursor = None
        if next_offset < len(records):
            next_cursor = self.cursor_codec.issue(
                principal,
                tool="export.read",
                query_sha256=query_sha256,
                page_size=limit,
                offset=next_offset,
                depth=depth + 1,
                chain_id=chain_id,
            )
        manifest_bytes = self.object_store.read_bytes(job.manifest_uri, 1_000_000)
        if hashlib.sha256(manifest_bytes).hexdigest() != job.manifest_sha256:
            raise ExportStateConflict("Export manifest checksum verification failed")
        manifest = self._verified_manifest(job, manifest_bytes)
        return ExportChunk(items, len(items), next_cursor, manifest)

    def _verified_manifest(self, job: DataExportJob, manifest_bytes: bytes) -> dict[str, Any]:
        try:
            envelope = json.loads(manifest_bytes)
            if not isinstance(envelope, dict) or envelope.get("schema") != "pharma.data-export-envelope.v1":
                raise ValueError
            payload = envelope["payload"]
            signature = envelope["signature"]
            if not isinstance(payload, dict) or not isinstance(signature, dict):
                raise ValueError
            manifest = SignedExportManifest(
                payload=payload,
                sha256=str(envelope["sha256"]),
                key_id=str(signature["key_id"]),
                signature=str(signature["value"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExportStateConflict("Export manifest is invalid") from exc
        bound = (
            signature.get("algorithm") == "HMAC-SHA256"
            and manifest.key_id == job.manifest_key_id
            and manifest.signature == job.manifest_signature
            and payload.get("job_id") == job.id
            and payload.get("artifact_sha256") == job.artifact_sha256
            and self.manifest_signer.verify(manifest)
        )
        if not bound:
            raise ExportStateConflict("Export manifest signature verification failed")
        return envelope

    def _repair_reservation(self, job: DataExportJob, principal: Principal) -> DataExportJob:
        if not job.approval_required and job.state == "pending_approval" and not job.reservation_id:
            return self._reserve_job(job, principal)
        return job

    def _reserve_job(self, job: DataExportJob, principal: Principal) -> DataExportJob:
        policy = self._policy(job.tenant_id, job.billing_account_id, lock=True)
        self._assert_license_policy_current(job, policy)
        usage = self._usage_service(principal)
        outcome = usage.reserve(
            ReserveCommand(
                billing_class=EXPORT_BILLING_CLASS,
                idempotency_key=f"export-reservation:{job.id}",
                request_arguments=self._reservation_arguments(job),
                requested_result_limit=job.max_records,
                max_billable_units=job.max_billable_units,
                request_id=new_uuid(),
            )
        )
        job = self._job_for_tenant(job.tenant_id, job.id, lock=True)
        job.reservation_id = outcome.reservation.id
        job.state = "queued"
        job.updated_at = datetime.now(UTC)
        self._outbox(job, "commercial.export_queued.v1")
        self.session.commit()
        return job

    def _cancel_locked(self, job: DataExportJob, principal: Principal) -> DataExportJob:
        if job.state in {"cancelled", "failed", "expired"}:
            return job
        if job.state == "completed":
            raise ExportStateConflict("Completed export jobs cannot be cancelled")
        if job.state == "running":
            job.state = "cancel_requested"
            job.cancel_requested_at = datetime.now(UTC)
            job.updated_at = job.cancel_requested_at
            self.session.commit()
            return job
        if job.reservation_id:
            self._usage_service(principal).release(
                job.reservation_id,
                reason="export cancelled before execution",
                request_id=new_uuid(),
            )
            job = self._job_for_tenant(job.tenant_id, job.id, lock=True)
        job.state = "cancelled"
        job.cancel_requested_at = datetime.now(UTC)
        job.completed_at = job.cancel_requested_at
        job.updated_at = job.cancel_requested_at
        self._outbox(job, "commercial.export_cancelled.v1")
        self.session.commit()
        return job

    def _cancel_worker_job(self, job: DataExportJob) -> DataExportJob:
        principal = self._job_principal(job)
        if job.reservation_id:
            self._usage_service(principal).release(
                job.reservation_id,
                reason="export cancellation acknowledged by worker",
                request_id=new_uuid(),
            )
            job = self._job_for_tenant(job.tenant_id, job.id, lock=True)
        job.state = "cancelled"
        job.completed_at = datetime.now(UTC)
        job.updated_at = job.completed_at
        self._outbox(job, "commercial.export_cancelled.v1")
        self.session.commit()
        return job

    def _usage_service(self, principal: Principal) -> CommercialUsageService:
        return CommercialUsageService(
            self.session,
            principal,
            reservation_lease_seconds=self.export_reservation_lease_seconds,
            max_result_bytes=self.max_durable_result_bytes,
            max_billable_units_per_call=self.max_billable_units_per_call,
            max_active_reservations_per_client=self.max_active_reservations_per_client,
            cursor_codec=self.cursor_codec,
        )

    def _bound_access(self, principal: Principal, now: datetime) -> tuple[AgentClient, CommercialSubscription]:
        if principal.actor_type not in {"agent", "api_key"} or not principal.commercial_client_id:
            raise CommercialAccessDenied("Governed exports require an Agent principal")
        client = self.session.scalar(
            select(AgentClient).where(
                AgentClient.tenant_id == principal.tenant_id,
                AgentClient.oauth_client_id == principal.commercial_client_id,
                AgentClient.active.is_(True),
            )
        )
        if client is None:
            raise CommercialNotConfigured("Agent client is not registered for exports")
        subject = self.session.scalar(
            select(AgentClientSubject).where(
                AgentClientSubject.tenant_id == principal.tenant_id,
                AgentClientSubject.agent_client_id == client.id,
                AgentClientSubject.actor_type == principal.actor_type,
                AgentClientSubject.subject_id == principal.actor_id,
                AgentClientSubject.active.is_(True),
            )
        )
        if subject is None:
            raise CommercialAccessDenied("Agent subject is not bound to the registered client")
        subscription = self.session.scalar(
            select(CommercialSubscription)
            .join(BillingAccount)
            .where(
                CommercialSubscription.tenant_id == principal.tenant_id,
                CommercialSubscription.agent_client_id == client.id,
                CommercialSubscription.status == SubscriptionStatus.ACTIVE,
                CommercialSubscription.starts_at <= now,
                (CommercialSubscription.ends_at.is_(None) | (CommercialSubscription.ends_at > now)),
                BillingAccount.status == BillingAccountStatus.ACTIVE,
            )
        )
        if subscription is None:
            raise CommercialNotConfigured("No active commercial subscription is available")
        return client, subscription

    def _policy(self, tenant_id: str, account_id: str, *, lock: bool) -> CommercialExportPolicy:
        statement = select(CommercialExportPolicy).where(
            CommercialExportPolicy.tenant_id == tenant_id,
            CommercialExportPolicy.billing_account_id == account_id,
        )
        if lock:
            statement = statement.with_for_update()
        policy = self.session.scalar(statement)
        if policy is None or not policy.enabled:
            raise CommercialNotConfigured("Customer export policy is not active")
        return policy

    def _field_policy(self, policy: CommercialExportPolicy) -> ExportFieldPolicy:
        try:
            return validate_export_field_policy(policy.field_policy)
        except ExportPolicyConfigurationError as exc:
            raise CommercialNotConfigured("Customer export field policy is invalid") from exc

    def _assert_license_policy_current(
        self,
        job: DataExportJob,
        policy: CommercialExportPolicy,
    ) -> None:
        field_policy = self._field_policy(policy)
        policy_sha256 = canonical_policy_sha256(field_policy.document())
        if (
            job.license_policy_version != field_policy.policy_version
            or job.license_policy_sha256 != policy_sha256
            or job.license_attribution != field_policy.attribution
        ):
            raise CommercialAccessDenied("Export license policy changed after this job was created")

    def _validate_request(
        self,
        policy: CommercialExportPolicy,
        field_policy: ExportFieldPolicy,
        command: CreateExportCommand,
    ) -> list[str]:
        if command.dataset not in DATASETS or command.dataset not in policy.allowed_datasets:
            raise ExportValidationError("Dataset is not allowed by the customer export policy")
        dataset_policy = field_policy.datasets.get(command.dataset)
        if dataset_policy is None:
            raise ExportValidationError("Dataset is not licensed for export")
        if command.export_format not in {"jsonl", "csv"} or command.export_format not in policy.allowed_formats:
            raise ExportValidationError("Export format is not allowed by the customer export policy")
        if not 1 <= command.max_records <= policy.max_records_per_job:
            raise ExportValidationError("Export record limit exceeds the customer policy")
        spec = DATASETS[command.dataset]
        fields = command.fields or list(dataset_policy.fields)
        if not fields or len(fields) != len(set(fields)) or "id" not in fields:
            raise ExportValidationError("Export fields must be unique and include id")
        if set(fields) - set(spec.fields) or set(fields) - set(dataset_policy.fields):
            raise ExportValidationError("Export contains unlicensed or unsupported fields")
        if len(_canonical_bytes(command.filters)) > 16_384:
            raise ExportValidationError("Export filters exceed the size limit")
        for key, value in command.filters.items():
            if key not in spec.filter_fields or key not in dataset_policy.filter_fields:
                raise ExportValidationError("Export contains an unlicensed or unsupported filter field")
            self._validate_filter_value(value)
        return fields

    @staticmethod
    def _validate_filter_value(value: Any) -> None:
        if isinstance(value, dict):
            if not value or set(value) - {"eq", "in", "gte", "lte"}:
                raise ExportValidationError("Export filter operator is unsupported")
            for operator, operand in value.items():
                if operator == "in":
                    if not isinstance(operand, list) or not 1 <= len(operand) <= 100:
                        raise ExportValidationError("Export in filter requires 1 to 100 values")
                    if any(not _is_filter_scalar(item) for item in operand):
                        raise ExportValidationError("Export filter values must be scalar")
                elif not _is_filter_scalar(operand):
                    raise ExportValidationError("Export filter values must be scalar")
            return
        if isinstance(value, list):
            if not 1 <= len(value) <= 100 or any(not _is_filter_scalar(item) for item in value):
                raise ExportValidationError("Export list filter requires 1 to 100 scalar values")
            return
        if not _is_filter_scalar(value):
            raise ExportValidationError("Export filter value must be scalar")

    def _query_records(self, job: DataExportJob) -> list[dict[str, Any]]:
        spec = DATASETS[job.dataset]
        columns = [getattr(spec.model, field) for field in job.fields_json]
        statement = select(*columns).where(spec.model.tenant_id == job.tenant_id)
        for name, value in job.filters_json.items():
            column: InstrumentedAttribute[Any] = getattr(spec.model, name)
            if isinstance(value, dict):
                for operator, operand in value.items():
                    if operator == "eq":
                        statement = statement.where(column == operand)
                    elif operator == "in":
                        statement = statement.where(column.in_(operand))
                    elif operator == "gte":
                        statement = statement.where(column >= operand)
                    elif operator == "lte":
                        statement = statement.where(column <= operand)
            elif isinstance(value, list):
                statement = statement.where(column.in_(value))
            else:
                statement = statement.where(column == value)
        rows = self.session.execute(statement.order_by(spec.model.id).limit(job.max_records)).all()
        return [{field: _json_value(value) for field, value in zip(job.fields_json, row, strict=True)} for row in rows]

    @staticmethod
    def _encode_records(export_format: str, fields: list[str], records: list[dict[str, Any]]) -> bytes:
        if export_format == "jsonl":
            return b"".join(_canonical_bytes(record) + b"\n" for record in records)
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _csv_value(value) for key, value in record.items()})
        return buffer.getvalue().encode("utf-8")

    @staticmethod
    def _decode_records(export_format: str, payload: bytes) -> list[dict[str, Any]]:
        try:
            text = payload.decode("utf-8")
            if export_format == "jsonl":
                return [json.loads(line) for line in text.splitlines() if line]
            return [dict(row) for row in csv.DictReader(io.StringIO(text, newline=""))]
        except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
            raise ExportStateConflict("Export artifact cannot be decoded") from exc

    def _owned_job(self, principal: Principal, job_id: str, *, lock: bool) -> DataExportJob:
        client, _ = self._bound_access(principal, datetime.now(UTC))
        statement = select(DataExportJob).where(
            DataExportJob.tenant_id == principal.tenant_id,
            DataExportJob.id == job_id,
            DataExportJob.agent_client_id == client.id,
            DataExportJob.actor_type == principal.actor_type,
            DataExportJob.subject_id == principal.actor_id,
        )
        if lock:
            statement = statement.with_for_update()
        job = self.session.scalar(statement)
        if job is None:
            raise ExportNotFound("Export job is unavailable for this Agent subject")
        return job

    def _job_for_tenant(self, tenant_id: str, job_id: str, *, lock: bool) -> DataExportJob:
        statement = select(DataExportJob).where(
            DataExportJob.tenant_id == tenant_id,
            DataExportJob.id == job_id,
        )
        if lock:
            statement = statement.with_for_update()
        job = self.session.scalar(statement)
        if job is None:
            raise ExportNotFound("Export job does not exist")
        return job

    def _job_principal(self, job: DataExportJob) -> Principal:
        client = self.session.get(AgentClient, job.agent_client_id)
        if client is None or not client.active:
            raise CommercialNotConfigured("Export Agent client is inactive")
        return Principal(
            tenant_id=job.tenant_id,
            actor_id=job.subject_id,
            actor_type=job.actor_type,  # type: ignore[arg-type]
            scopes=frozenset({"data:export"}),
            client_id=client.oauth_client_id,
        )

    @staticmethod
    def _reservation_arguments(job: DataExportJob) -> dict[str, Any]:
        return {
            "dataset": job.dataset,
            "format": job.export_format,
            "filters": job.filters_json,
            "fields": job.fields_json,
        }

    def _audit(
        self,
        job: DataExportJob,
        actor_type: str,
        actor_id: str,
        action: str,
        outcome: str,
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=job.tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                resource_type="data_export_job",
                resource_id=job.id,
                outcome=outcome,
                request_id=new_uuid(),
                details={"dataset": job.dataset, "state": job.state},
            )
        )

    def _outbox(self, job: DataExportJob, event_type: str) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=job.tenant_id,
                aggregate_type="data_export_job",
                aggregate_id=job.id,
                event_type=event_type,
                payload={"job_id": job.id, "dataset": job.dataset, "state": job.state},
            )
        )


def export_job_view(job: DataExportJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "dataset": job.dataset,
        "format": job.export_format,
        "fields": job.fields_json,
        "filters": job.filters_json,
        "max_records": job.max_records,
        "license_policy_version": job.license_policy_version,
        "license_policy_sha256": job.license_policy_sha256,
        "license_attribution": job.license_attribution,
        "record_count": job.record_count,
        "state": job.state,
        "approval_required": job.approval_required,
        "approved_by": job.approved_by,
        "approved_at": job.approved_at,
        "artifact_bytes": job.artifact_bytes,
        "artifact_sha256": job.artifact_sha256,
        "manifest_sha256": job.manifest_sha256,
        "manifest_signature": job.manifest_signature,
        "manifest_key_id": job.manifest_key_id,
        "failure_code": job.failure_code,
        "failure_message": job.failure_message,
        "requested_at": job.requested_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "expires_at": job.expires_at,
    }


def build_export_service(session: Session, settings: Settings) -> CommercialExportService:
    return CommercialExportService(
        session,
        build_object_store(settings),
        ExportManifestSigner(
            settings.effective_export_manifest_signing_secret,
            key_id=settings.export_manifest_signing_key_id,
        ),
        SignedCursorCodec(
            settings.effective_mcp_cursor_signing_secret,
            ttl_seconds=settings.mcp_cursor_ttl_seconds,
            max_token_chars=settings.mcp_cursor_max_token_chars,
        ),
        export_reservation_lease_seconds=settings.export_reservation_lease_seconds,
        max_durable_result_bytes=settings.mcp_max_durable_result_bytes,
        max_billable_units_per_call=settings.mcp_max_billable_units_per_call,
        max_active_reservations_per_client=settings.mcp_max_active_reservations_per_client,
        read_page_size_max=settings.export_read_page_size_max,
    )


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_value,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExportValidationError("Export payload is not valid canonical JSON") from exc


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool | dict | list):
        return value
    if isinstance(value, datetime):
        return _as_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported export value: {type(value).__name__}")


def _csv_value(value: Any) -> Any:
    if isinstance(value, dict | list):
        return _canonical_bytes(value).decode("ascii")
    if value is None:
        return ""
    return value


def _is_filter_scalar(value: Any) -> bool:
    return value is None or (not isinstance(value, bool) and isinstance(value, str | int | float))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
