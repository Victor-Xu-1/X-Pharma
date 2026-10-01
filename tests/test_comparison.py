from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Generator
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.comparison.exports import (
    WorkspaceComparisonExportService,
    WorkspaceExportConflict,
    WorkspaceExportDenied,
    WorkspaceExportNotConfigured,
)
from pharma_intel.comparison.service import (
    ComparisonSetConflict,
    ComparisonSetLimitExceeded,
    ComparisonSetNotFound,
    ComparisonSetService,
)
from pharma_intel.db import get_session
from pharma_intel.models import (
    ComparisonSetVersion,
    EntityType,
    SavedSearchVisibility,
    Tenant,
    User,
    UserRole,
    WorkspaceExportEvent,
)
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import (
    ComparisonSetCreate,
    EntityCreate,
    WorkspaceDomainExportCreate,
    WorkspaceExportCreate,
    WorkspaceExportPolicyUpsert,
)
from pharma_intel.security import Principal, require_principal
from pharma_intel.sorting import SortClause


def _user(session: Session, tenant: Tenant, suffix: str, role: UserRole = UserRole.ANALYST) -> User:
    user = create_account(
        tenant_id=tenant.id,
        email=f"comparison-{suffix}@example.test",
        normalized_email=f"comparison-{suffix}@example.test",
        display_name=suffix,
        password_hash="not-used",  # noqa: S106
        role=role,
    )
    session.add(user)
    session.commit()
    return user


def _policy() -> WorkspaceExportPolicyUpsert:
    return WorkspaceExportPolicyUpsert(
        policy_version="workspace-export-2026-01",
        enabled=True,
        allowed_formats=["csv", "json", "xlsx"],
        allowed_fields=[
            "position",
            "id",
            "entity_type",
            "name",
            "external_ids",
            "entities.id",
            "entities.entity_type",
            "entities.name",
            "entities.review_status",
        ],
        max_records_per_export=20,
        attribution="Licensed for Test Tenant internal use",
    )


def test_comparison_set_visibility_versioning_and_bounded_members(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "owner")
    colleague = _user(session, tenant, "colleague")
    other_tenant = Tenant(slug="comparison-other", name="Other")
    session.add(other_tenant)
    session.commit()
    outsider = _user(session, other_tenant, "outsider")
    entities = [
        EntityRepository(session, tenant.id).create(
            EntityCreate(entity_type=EntityType.TARGET, name=f"Target {index:02d}")
        )
        for index in range(21)
    ]
    service = ComparisonSetService(session, tenant.id, owner.id, include_unpublished=True)
    private = service.create_set(ComparisonSetCreate(name="Private set"))
    assert ComparisonSetService(session, tenant.id, colleague.id, include_unpublished=True).list_sets() == []
    shared = service.create_set(ComparisonSetCreate(name="Shared set", visibility=SavedSearchVisibility.TENANT))
    assert [
        item.item.id
        for item in ComparisonSetService(session, tenant.id, colleague.id, include_unpublished=True).list_sets()
    ] == [shared.item.id]
    with pytest.raises(ComparisonSetNotFound):
        ComparisonSetService(session, other_tenant.id, outsider.id, include_unpublished=True).get_set(shared.item.id)

    current = private
    for entity in entities[:20]:
        current = service.add_member(current.item.id, entity.id, expected_version=current.item.version)
    assert current.member_count == 20
    assert current.item.version == 21
    with pytest.raises(ComparisonSetConflict):
        service.remove_member(current.item.id, entities[0].id, expected_version=20)
    with pytest.raises(ComparisonSetLimitExceeded, match="limited to 20"):
        service.add_member(current.item.id, entities[20].id, expected_version=current.item.version)
    assert (
        session.scalar(
            select(func.count())
            .select_from(ComparisonSetVersion)
            .where(ComparisonSetVersion.comparison_set_id == current.item.id)
        )
        == 21
    )
    assert service.list_versions(current.item.id)[0].snapshot_json["member_entity_ids"] == [
        entity.id for entity in entities[:20]
    ]


def test_comparison_set_batch_add_is_atomic_and_creates_one_version(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "batch-owner")
    entities = [
        EntityRepository(session, tenant.id).create(
            EntityCreate(entity_type=EntityType.TARGET, name=f"Batch target {index}")
        )
        for index in range(3)
    ]
    service = ComparisonSetService(session, tenant.id, owner.id, include_unpublished=True)
    comparison = service.create_set(ComparisonSetCreate(name="Batch set"))

    updated = service.add_members(
        comparison.item.id,
        [entities[0].id, entities[1].id],
        expected_version=comparison.item.version,
    )

    assert updated.item.version == 2
    assert [cast(dict[str, object], member["entity"])["id"] for member in updated.members] == [
        entities[0].id,
        entities[1].id,
    ]
    assert (
        session.scalar(
            select(func.count())
            .select_from(ComparisonSetVersion)
            .where(ComparisonSetVersion.comparison_set_id == comparison.item.id)
        )
        == 2
    )
    with pytest.raises(ComparisonSetConflict, match="already"):
        service.add_members(
            comparison.item.id,
            [entities[1].id, entities[2].id],
            expected_version=updated.item.version,
        )
    session.rollback()
    unchanged = service.get_set(comparison.item.id)
    assert unchanged.item.version == 2
    assert [cast(dict[str, object], member["entity"])["id"] for member in unchanged.members] == [
        entities[0].id,
        entities[1].id,
    ]


def test_workspace_exports_are_policy_bound_reproducible_and_formula_safe(session: Session, tenant: Tenant) -> None:
    user = _user(session, tenant, "exporter")
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(
            entity_type=EntityType.ORGANIZATION,
            name='=HYPERLINK("https://example.test")',
            external_ids={"registry": "ORG-1"},
        )
    )
    comparison_service = ComparisonSetService(session, tenant.id, user.id, include_unpublished=True)
    comparison = comparison_service.create_set(ComparisonSetCreate(name="Export set"))
    comparison = comparison_service.add_member(comparison.item.id, entity.id, expected_version=comparison.item.version)
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    with pytest.raises(WorkspaceExportNotConfigured):
        export_service.export_comparison_set(
            comparison.item.id,
            WorkspaceExportCreate(
                expected_version=comparison.item.version,
                export_format="json",
                fields=["id", "entity_type", "name"],
                idempotency_key="comparison-export-missing-policy",
            ),
        )
    policy = export_service.upsert_policy(_policy())
    assert export_service.policy_view(policy)["policy_sha256"]

    artifacts = {}
    for export_format in ("json", "csv", "xlsx"):
        command = WorkspaceExportCreate(
            expected_version=comparison.item.version,
            export_format=export_format,
            fields=["position", "id", "entity_type", "name", "external_ids"],
            idempotency_key=f"comparison-export-{export_format}-0001",
        )
        artifact = export_service.export_comparison_set(comparison.item.id, command)
        replay = export_service.export_comparison_set(comparison.item.id, command)
        assert replay.replayed is True
        assert replay.event_id == artifact.event_id
        assert replay.content == artifact.content
        assert hashlib.sha256(artifact.content).hexdigest() == artifact.content_sha256
        artifacts[export_format] = artifact.content

    document = json.loads(artifacts["json"])
    assert document["schema"] == "pharma.workspace-comparison-export.v1"
    assert document["records"][0]["name"].startswith("=HYPERLINK")
    rows = list(csv.DictReader(io.StringIO(artifacts["csv"].decode("utf-8-sig"))))
    assert rows[0]["entity_type"] == "organization"
    assert rows[0]["name"].startswith("'=HYPERLINK")
    with zipfile.ZipFile(io.BytesIO(artifacts["xlsx"])) as workbook:
        worksheets = b"".join(
            workbook.read(name) for name in workbook.namelist() if name.startswith("xl/worksheets/sheet")
        )
        assert b"<f" not in worksheets
    assert session.scalar(select(func.count()).select_from(WorkspaceExportEvent)) == 3

    with pytest.raises(WorkspaceExportConflict):
        export_service.export_comparison_set(
            comparison.item.id,
            WorkspaceExportCreate(
                expected_version=comparison.item.version,
                export_format="json",
                fields=["id", "entity_type", "name", "external_ids"],
                idempotency_key="comparison-export-json-0001",
            ),
        )
    with pytest.raises(WorkspaceExportDenied):
        export_service.export_comparison_set(
            comparison.item.id,
            WorkspaceExportCreate(
                expected_version=comparison.item.version,
                export_format="json",
                fields=["id", "entity_type", "name", "description"],
                idempotency_key="comparison-export-denied-field",
            ),
        )


def test_workspace_domain_exports_reuse_governed_query_and_field_policy(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(session, tenant, "domain-exporter")
    target = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="Domain export target")
    )
    organization = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.ORGANIZATION, name="Domain export organization")
    )
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    export_service.upsert_policy(_policy())
    command = WorkspaceDomainExportCreate(
        dataset="entities",
        query={
            "q": "Domain export",
            "entity_types": ["target", "organization"],
            "sort_by": "name",
            "sort_direction": "asc",
        },
        export_format="json",
        fields=["id", "entity_type", "name", "review_status"],
        max_records=20,
        idempotency_key="domain-export-entities-0001",
    )

    artifact = export_service.export_domain_query(command)
    replay_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    monkeypatch.setattr(
        replay_service,
        "_domain_records",
        lambda _: pytest.fail("an idempotent replay must not rerun the mutable domain query"),
    )
    replay = replay_service.export_domain_query(command)

    assert replay.replayed is True
    assert replay.event_id == artifact.event_id
    document = json.loads(artifact.content)
    assert document["schema"] == "pharma.workspace-domain-export.v1"
    assert document["dataset"] == "entities"
    assert document["query"] == command.query
    assert document["records"] == [
        {
            "entity_type": "organization",
            "id": organization.id,
            "name": "Domain export organization",
            "review_status": "draft",
        },
        {
            "entity_type": "target",
            "id": target.id,
            "name": "Domain export target",
            "review_status": "draft",
        },
    ]
    event = session.get(WorkspaceExportEvent, artifact.event_id)
    assert event is not None
    assert event.export_kind == "domain"
    assert event.dataset == "entities"
    assert event.query_json == command.query
    assert event.comparison_set_id is None
    assert event.comparison_set_version is None

    with pytest.raises(WorkspaceExportDenied, match="fields"):
        export_service.export_domain_query(
            command.model_copy(
                update={
                    "fields": ["id", "name", "description"],
                    "idempotency_key": "domain-export-denied-field-0001",
                }
            )
        )
    with pytest.raises(WorkspaceExportDenied, match="query"):
        export_service.export_domain_query(
            command.model_copy(
                update={
                    "query": {"unsupported": "value"},
                    "idempotency_key": "domain-export-invalid-query-0001",
                }
            )
        )


def test_workspace_trial_export_passes_normalized_entity_or_query_to_engine(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(session, tenant, "trial-domain-exporter")
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    export_service.upsert_policy(
        _policy().model_copy(
            update={
                "allowed_formats": ["json"],
                "allowed_fields": [
                    "position",
                    "id",
                    "entity_type",
                    "name",
                    "external_ids",
                    "trials.id",
                    "trials.registry_id",
                ],
            }
        )
    )
    first_id = "550e8400-e29b-41d4-a716-446655440003"
    second_id = "550e8400-e29b-41d4-a716-446655440004"
    captured: dict[str, object] = {}

    def search_trials(_service: object, *args: object, **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(items=[], query_schema_version="pharma.clinical_trial.search.v10")

    monkeypatch.setattr(
        "pharma_intel.comparison.exports.IntelligenceService.search_clinical_trials",
        search_trials,
    )
    command = WorkspaceDomainExportCreate(
        dataset="trials",
        query={
            "investigational_drug_entity_ids": [second_id, first_id],
            "combination_drug_entity_ids": [first_id],
            "investigational_target_entity_ids": [second_id],
            "combination_target_entity_ids": [first_id],
            "linked_drug_modality": ["antibody"],
            "linked_drug_innovation_type": ["innovative"],
            "linked_drug_category": ["biologic"],
            "linked_drug_program_tag": ["first_in_class"],
            "linked_drug_global_phase": "phase_3",
            "linked_drug_organization_country_region": "CN",
            "role_entity_ids": [second_id, first_id],
            "role_entity_role": "investigational_drug",
            "sort": ["overall_status:asc", "registry_id:desc"],
        },
        export_format="json",
        fields=["id", "registry_id"],
        max_records=20,
        idempotency_key="domain-export-trial-or-0001",
    )

    with pytest.raises(WorkspaceExportDenied, match="Empty workspace domain query results"):
        export_service.export_domain_query(command)

    assert captured["kwargs"] == {
        "results_posted_from": None,
        "results_posted_to": None,
        "result_evaluation": None,
        "acronym": None,
        "initiation_type": None,
        "therapy_line": None,
        "investigational_drug": None,
        "combination_drug": None,
        "investigational_target": None,
        "combination_target": None,
        "investigational_drug_entity_ids": [first_id, second_id],
        "combination_drug_entity_ids": [first_id],
        "investigational_target_entity_ids": [second_id],
        "combination_target_entity_ids": [first_id],
        "linked_drug_modality": ["antibody"],
        "linked_drug_innovation_type": ["innovative"],
        "linked_drug_category": ["biologic"],
        "linked_drug_program_tag": ["first_in_class"],
        "linked_drug_global_phase": "phase_3",
        "linked_drug_organization_country_region": "CN",
        "role_entity_id": None,
        "role_entity_ids": [first_id, second_id],
        "role_entity_role": "investigational_drug",
        "has_key_result": None,
        "publication_id": None,
        "conference": None,
        "disclosed_from": None,
        "disclosed_to": None,
        "sort_by": "overall_status",
        "sort_direction": "asc",
        "sort": (
            SortClause(field="overall_status", direction="asc"),
            SortClause(field="registry_id", direction="desc"),
        ),
    }


def test_workspace_pipeline_export_preserves_governed_organization_relationship_filters(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(session, tenant, "pipeline-domain-exporter")
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    export_service.upsert_policy(
        _policy().model_copy(
            update={
                "allowed_formats": ["json"],
                "allowed_fields": ["position", "id", "entity_type", "name", "pipelines.id"],
            }
        )
    )
    captured: dict[str, object] = {}
    drug_id = "550e8400-e29b-41d4-a716-446655440020"

    def search_programs(_service: object, *args: object, **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(items=[], query_schema_version="pharma.pipeline.search.v13")

    monkeypatch.setattr("pharma_intel.comparison.exports.IntelligenceService.search_programs", search_programs)
    command = WorkspaceDomainExportCreate(
        dataset="pipelines",
        query={
            "drug_entity_id": drug_id,
            "program_status": "active",
            "organization_role": "collaborator",
            "organization_type": "biotech",
            "organization_country_region": "US",
        },
        export_format="json",
        fields=["id"],
        max_records=20,
        idempotency_key="domain-export-pipeline-organization-0001",
    )

    with pytest.raises(WorkspaceExportDenied, match="Empty workspace domain query results"):
        export_service.export_domain_query(command)

    kwargs = cast(dict[str, object], captured["kwargs"])
    assert kwargs["drug_entity_id"] == drug_id
    assert kwargs["program_status"] == "active"
    assert kwargs["organization_role"] == "collaborator"
    assert kwargs["organization_type"] == "biotech"
    assert kwargs["organization_country_region"] == "US"


def test_workspace_deal_export_passes_asset_and_entity_filters_to_engine(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deal export must execute the same asset/entity conditions the list applied.

    These five parameters were silently dropped by the web export whitelist, so the
    export produced a superset of the on-screen result set. The engine call is the
    contract: every condition present in the command query must reach search_deals.
    """

    user = _user(session, tenant, "deal-domain-exporter")
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    export_service.upsert_policy(
        _policy().model_copy(
            update={
                "allowed_formats": ["json"],
                "allowed_fields": ["position", "id", "entity_type", "name", "external_ids", "deals.id", "deals.name"],
            }
        )
    )
    asset_id = "550e8400-e29b-41d4-a716-446655440021"
    target_id = "550e8400-e29b-41d4-a716-446655440022"
    disease_id = "550e8400-e29b-41d4-a716-446655440023"
    captured: dict[str, object] = {}

    def search_deals(_service: object, *args: object, **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(items=[], query_schema_version="pharma.deal.search.v8")

    monkeypatch.setattr("pharma_intel.comparison.exports.IntelligenceService.search_deals", search_deals)
    command = WorkspaceDomainExportCreate(
        dataset="deals",
        query={
            "asset_entity_id": asset_id,
            "target_entity_id": target_id,
            "disease_entity_id": disease_id,
            "asset_modality": ["antibody"],
            "asset_program_tag": ["first_in_class", "new_modality"],
            "sort_by": "announced_at",
            "sort_direction": "desc",
        },
        export_format="json",
        fields=["id", "name"],
        max_records=20,
        idempotency_key="domain-export-deal-asset-0001",
    )

    with pytest.raises(WorkspaceExportDenied, match="Empty workspace domain query results"):
        export_service.export_domain_query(command)

    kwargs = cast(dict[str, object], captured["kwargs"])
    assert kwargs["asset_entity_id"] == asset_id
    assert kwargs["target_entity_id"] == target_id
    assert kwargs["disease_entity_id"] == disease_id
    assert kwargs["asset_modality"] == ["antibody"]
    assert kwargs["asset_program_tag"] == ["first_in_class", "new_modality"]


def test_workspace_epidemiology_export_passes_disease_filter_to_engine(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The epidemiology export must honor the canonical disease condition the list used."""

    user = _user(session, tenant, "epi-domain-exporter")
    export_service = WorkspaceComparisonExportService(session, tenant.id, user.id, include_unpublished=True)
    export_service.upsert_policy(
        _policy().model_copy(
            update={
                "allowed_formats": ["json"],
                "allowed_fields": [
                    "position",
                    "id",
                    "entity_type",
                    "name",
                    "external_ids",
                    "epidemiology.id",
                    "epidemiology.measure",
                ],
            }
        )
    )
    disease_id = "550e8400-e29b-41d4-a716-446655440031"
    captured: dict[str, object] = {}

    def search_epidemiology(_service: object, *args: object, **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(items=[], query_schema_version="pharma.epidemiology.search.v3")

    monkeypatch.setattr(
        "pharma_intel.comparison.exports.IntelligenceService.search_epidemiology_observations",
        search_epidemiology,
    )
    command = WorkspaceDomainExportCreate(
        dataset="epidemiology",
        query={
            "disease_entity_id": disease_id,
            "measure": "prevalence",
            "sort_by": "period_end",
            "sort_direction": "desc",
        },
        export_format="json",
        fields=["id", "measure"],
        max_records=20,
        idempotency_key="domain-export-epi-disease-0001",
    )

    with pytest.raises(WorkspaceExportDenied, match="Empty workspace domain query results"):
        export_service.export_domain_query(command)

    kwargs = cast(dict[str, object], captured["kwargs"])
    assert kwargs["disease_entity_id"] == disease_id


def test_comparison_api_requires_human_session_and_admin_policy_scope(session: Session, tenant: Tenant) -> None:
    user = _user(session, tenant, "api", UserRole.ADMIN)
    entity = EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="API Target"))
    batch_entities = [
        EntityRepository(session, tenant.id).create(
            EntityCreate(entity_type=EntityType.DRUG, name=f"API batch drug {index}")
        )
        for index in range(2)
    ]

    def session_override() -> Generator[Session]:
        yield session

    def admin_override() -> Principal:
        return Principal(tenant.id, user.id, "user", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = admin_override
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/comparison-sets",
                json={"name": "API comparison", "visibility": "tenant"},
            )
            assert created.status_code == 201
            item = created.json()
            added = client.post(
                f"/api/v1/comparison-sets/{item['id']}/members",
                json={"entity_id": entity.id, "expected_version": item["version"]},
            )
            assert added.status_code == 200
            item = added.json()
            assert item["members"][0]["entity"]["name"] == "API Target"
            batch_added = client.post(
                f"/api/v1/comparison-sets/{item['id']}/members/batch",
                json={
                    "entity_ids": [batch_entities[0].id, batch_entities[1].id],
                    "expected_version": item["version"],
                },
            )
            assert batch_added.status_code == 200
            item = batch_added.json()
            assert item["version"] == 3
            assert [member["entity"]["name"] for member in item["members"]] == [
                "API Target",
                "API batch drug 0",
                "API batch drug 1",
            ]
            duplicate_batch = client.post(
                f"/api/v1/comparison-sets/{item['id']}/members/batch",
                json={"entity_ids": [entity.id, entity.id], "expected_version": item["version"]},
            )
            assert duplicate_batch.status_code == 422
            configured = client.post("/api/v1/admin/workspace-export-policy", json=_policy().model_dump(mode="json"))
            assert configured.status_code == 200
            exported = client.post(
                f"/api/v1/comparison-sets/{item['id']}/export",
                json={
                    "expected_version": item["version"],
                    "export_format": "json",
                    "fields": ["id", "entity_type", "name"],
                    "idempotency_key": "api-comparison-export-0001",
                },
            )
            assert exported.status_code == 200
            assert exported.headers["x-content-sha256"] == hashlib.sha256(exported.content).hexdigest()
            domain_exported = client.post(
                "/api/v1/workspace/domain-exports",
                json={
                    "dataset": "entities",
                    "query": {"q": "API Target", "entity_type": "target"},
                    "export_format": "json",
                    "fields": ["id", "entity_type", "name"],
                    "max_records": 20,
                    "idempotency_key": "api-domain-export-0001",
                },
            )
            assert domain_exported.status_code == 200
            assert json.loads(domain_exported.content)["records"][0]["id"] == entity.id
            assert client.get(f"/api/v1/comparison-sets/{item['id']}/versions").status_code == 200

        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id, "agent-1", "agent", frozenset({"collections:read", "workspace:export"})
        )
        with TestClient(app) as client:
            assert client.get("/api/v1/comparison-sets").status_code == 403
            assert client.get("/api/v1/workspace/export-policy").status_code == 403
    finally:
        app.dependency_overrides.clear()
