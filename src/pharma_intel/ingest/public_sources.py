from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import select

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.ingest.chembl import CHEMBL_API_ROOT, ChemblRoutingRule
from pharma_intel.ingest.clinicaltrials import CLINICALTRIALS_GOV_STUDIES_URL, ClinicalTrialsGovRoutingRule
from pharma_intel.ingest.connectors import SourceConnectorRegistry
from pharma_intel.ingest.pubmed import PUBMED_EUTILITIES_ROOT, PubMedRoutingRule
from pharma_intel.ingest.source_routing import canonical_routing_rules, routing_scope_identity
from pharma_intel.licensing import EvidenceLicensePolicy
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceState,
    DataSourceType,
    SourceAsset,
    Tenant,
    TenantDataset,
)


@dataclass(frozen=True)
class PublicSourceDefinition:
    source_type: DataSourceType
    root_uri: str
    name: str
    dataset_key: str
    scope: str
    license_id: str
    policy_version: str
    attribution: str
    metadata: dict[str, str]
    pattern: str
    max_file_bytes: int
    rate_limit: int
    freshness: int = 172_800


_EVIDENCE_FIELDS = [
    "content",
    "content_sha256",
    "document_name",
    "evidence_claim_id",
    "locator",
    "review_status",
    "source_document_id",
    "source_uri",
    "source_version_id",
    "subject_entity_id",
]


def _register(
    tenant_slug: str,
    definition: PublicSourceDefinition,
    rule: dict[str, Any],
    scan_interval_seconds: int,
    scopes: list[str] | None = None,
) -> DataSource:
    if not 60 <= scan_interval_seconds <= 31_536_000:
        raise ValueError("scan_interval_seconds must be between 60 and 31536000")
    settings = get_settings()
    registry = SourceConnectorRegistry(settings)
    factory = get_session_factory()
    with factory() as identity_session:
        tenant = identity_session.scalar(select(Tenant).where(Tenant.slug == tenant_slug, Tenant.active.is_(True)))
    if tenant is None:
        raise ValueError("Active tenant was not found")
    with factory() as session:
        set_tenant_context(session, tenant.id)
        dataset = session.scalar(
            select(TenantDataset).where(
                TenantDataset.tenant_id == tenant.id, TenantDataset.dataset_key == definition.dataset_key
            )
        )
        if dataset is None:
            dataset = TenantDataset(
                tenant_id=tenant.id,
                dataset_key=definition.dataset_key,
                display_name=definition.name,
                license_policy=EvidenceLicensePolicy(
                    license_id=definition.license_id,
                    policy_version=definition.policy_version,
                    permitted_channels=["web", "mcp"],
                    allowed_fields=_EVIDENCE_FIELDS,
                    max_content_chars=5000,
                    attribution=definition.attribution,
                    metadata=definition.metadata,
                ).document(),
            )
            session.add(dataset)
        else:
            policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
            if not dataset.active or not (
                policy.permits("web", datetime.now(UTC)) or policy.permits("mcp", datetime.now(UTC))
            ):
                raise ValueError("Existing dataset must be active and currently licensed before source registration")
        source = session.scalar(
            select(DataSource)
            .where(DataSource.tenant_id == tenant.id, DataSource.root_uri == definition.root_uri)
            .with_for_update()
        )
        routing_rules = [rule]
        authorization_scopes = scopes or [definition.scope]
        changed = source is None
        if source is None:
            source = DataSource(
                tenant_id=tenant.id,
                name=definition.name,
                source_type=definition.source_type,
                root_uri=definition.root_uri,
                owner="X-Pharma public data operations",
                data_classification="public",
                authorization_scopes=authorization_scopes,
                dataset_key=definition.dataset_key,
                include_globs=[definition.pattern],
                exclude_globs=[],
                routing_rules=routing_rules,
                stable_seconds=0,
                max_file_bytes=definition.max_file_bytes,
                scan_interval_seconds=scan_interval_seconds,
                expected_freshness_seconds=definition.freshness,
                rate_limit_per_minute=definition.rate_limit,
            )
            session.add(source)
        else:
            if source.source_type != definition.source_type or source.dataset_key != definition.dataset_key:
                raise ValueError("Official source root is already assigned to another connector or dataset")
            routing_changed = canonical_routing_rules(source.source_type, source.routing_rules) != routing_rules
            if routing_scope_identity(source.source_type, source.routing_rules) != routing_scope_identity(
                source.source_type, routing_rules
            ) and session.scalar(
                select(SourceAsset.id)
                .where(SourceAsset.tenant_id == tenant.id, SourceAsset.data_source_id == source.id)
                .limit(1)
            ):
                raise ValueError("Changing an acquired source query or history scope requires a governed migration")
            changed = (
                routing_changed
                or source.authorization_scopes != authorization_scopes
                or source.scan_interval_seconds != scan_interval_seconds
                or source.state != DataSourceState.ACTIVE
            )
            if routing_changed:
                source.connector_cursor = {}
                source.last_cursor_at = None
            source.routing_rules = routing_rules
            source.authorization_scopes = authorization_scopes
            source.scan_interval_seconds = scan_interval_seconds
            if changed:
                source.config_version += 1
            source.state = DataSourceState.ACTIVE
        configuration_errors = registry.get(source.source_type).validate_configuration(source)
        if configuration_errors:
            raise ValueError("; ".join(configuration_errors))
        if changed:
            session.flush()
            session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    actor_type="system",
                    actor_id="pharma-ingest",
                    action="data_source.public_registration",
                    resource_type="data_source",
                    resource_id=source.id,
                    outcome="success",
                    request_id=str(uuid.uuid4()),
                    details={
                        "source_type": source.source_type.value,
                        "config_version": source.config_version,
                        "sync_mode": rule.get("sync_mode", "snapshot"),
                    },
                )
            )
        session.commit()
        session.refresh(source)
        return source


def register_clinicaltrials_gov_source(
    *,
    tenant_slug: str,
    query_term: str,
    max_records: int,
    page_size: int,
    scan_interval_seconds: int = 86_400,
    sync_mode: Literal["snapshot", "continuous"] = "snapshot",
    start_date: date | None = None,
) -> DataSource:
    rule = ClinicalTrialsGovRoutingRule(
        query_term=query_term,
        max_records=max_records,
        page_size=page_size,
        sync_mode=sync_mode,
        start_date=start_date,
    )
    rule = rule.model_copy(update={"page_size": min(page_size, max_records)})
    definition = PublicSourceDefinition(
        DataSourceType.CLINICALTRIALS_GOV,
        CLINICALTRIALS_GOV_STUDIES_URL,
        "ClinicalTrials.gov official API",
        "clinical_trials",
        "public:clinicaltrials-gov",
        "clinicaltrials-gov-public-data",
        "terms-2023-01-31",
        "ClinicalTrials.gov, U.S. National Library of Medicine",
        {"source": "https://clinicaltrials.gov/", "terms": "https://clinicaltrials.gov/about-site/terms-conditions"},
        "studies/*.json",
        10_000_000,
        60,
    )
    return _register(tenant_slug, definition, rule.document(), scan_interval_seconds)


def register_chembl_source(
    *,
    tenant_slug: str,
    target_chembl_id: str,
    max_records: int,
    page_size: int,
    scan_interval_seconds: int = 86_400,
    sync_mode: Literal["snapshot", "continuous"] = "snapshot",
) -> DataSource:
    rule = ChemblRoutingRule(
        target_chembl_id=target_chembl_id,
        max_records=max_records,
        page_size=page_size,
        sync_mode=sync_mode,
    )
    definition = PublicSourceDefinition(
        DataSourceType.CHEMBL,
        CHEMBL_API_ROOT,
        f"ChEMBL official API ({rule.target_chembl_id})",
        "chembl",
        "public:chembl",
        "chembl-cc-by-sa-3.0",
        "chembl-rest-2026-08",
        "ChEMBL, EMBL-EBI, CC BY-SA 3.0",
        {"source": CHEMBL_API_ROOT, "license": "https://creativecommons.org/licenses/by-sa/3.0/"},
        "mechanisms/*.json",
        1_000_000,
        60,
        freshness=604_800,
    )
    return _register(tenant_slug, definition, rule.document(), scan_interval_seconds)


def register_pubmed_source(
    *,
    tenant_slug: str,
    query_term: str,
    max_records: int,
    page_size: int,
    include_abstract: bool,
    scan_interval_seconds: int = 86_400,
) -> DataSource:
    rule = PubMedRoutingRule(
        query_term=query_term,
        max_records=max_records,
        page_size=page_size,
        include_abstract=include_abstract,
    )
    rule = rule.model_copy(update={"page_size": min(page_size, max_records)})
    definition = PublicSourceDefinition(
        DataSourceType.PUBMED,
        PUBMED_EUTILITIES_ROOT,
        "NCBI PubMed official E-utilities",
        "literature",
        "public:ncbi-pubmed-metadata",
        "ncbi-pubmed-public-metadata",
        "pilot-2026-07-30",
        "NCBI PubMed, U.S. National Library of Medicine",
        {
            "source": "https://pubmed.ncbi.nlm.nih.gov/",
            "policy": "https://www.ncbi.nlm.nih.gov/home/about/policies/",
            "abstracts_included": str(include_abstract).lower(),
        },
        "articles/*.md",
        2_000_000,
        120,
    )
    scopes = [definition.scope] + (["public:ncbi-pubmed-abstracts"] if include_abstract else [])
    return _register(tenant_slug, definition, rule.model_dump(mode="json"), scan_interval_seconds, scopes)
