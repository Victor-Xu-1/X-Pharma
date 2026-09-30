from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    Entity,
    EntityType,
    RegulatoryDesignationType,
    RegulatoryEvent,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    Tenant,
)
from pharma_intel.sorting import SortClause


def _entity(session: Session, tenant: Tenant, entity_type: EntityType, name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=entity_type,
        name=name,
        normalized_name=name.casefold(),
    )
    session.add(entity)
    session.flush()
    return entity


def _event(
    session: Session,
    tenant: Tenant,
    subject: Entity,
    *,
    identifier: str,
    agency: str,
    jurisdiction: str,
    event_type: str,
    status: str,
    decision_day: int,
    indication: Entity | None = None,
    organization: Entity | None = None,
    designation_type: RegulatoryDesignationType | None = None,
    label_change_type: RegulatoryLabelChangeType | None = None,
    label_version: str | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: RegulatorySafetySignalType | None = None,
    safety_severity: RegulatorySafetySeverity | None = None,
    safety_status: RegulatorySafetyStatus | None = None,
) -> RegulatoryEvent:
    event = RegulatoryEvent(
        tenant_id=tenant.id,
        subject_entity_id=subject.id,
        agency=agency,
        jurisdiction=jurisdiction,
        event_identifier=identifier,
        application_number=f"NDA-{identifier}",
        event_type=event_type,
        status=status,
        title=f"{subject.name} {event_type}",
        decision_date=datetime(2026, 2, decision_day, tzinfo=UTC),
        designation_type=designation_type.value if designation_type else None,
        label_change_type=label_change_type.value if label_change_type else None,
        label_version=label_version,
        label_effective_at=datetime(2026, 2, decision_day + 1, tzinfo=UTC) if label_change_type else None,
        approved_population="Adults with EGFR exon 19 deletion" if label_change_type else None,
        line_of_therapy="first_line" if label_change_type else None,
        biomarker="EGFR exon 19 deletion" if label_change_type else None,
        route_of_administration="oral" if label_change_type else None,
        dosage_form="tablet" if label_change_type else None,
        has_boxed_warning=has_boxed_warning,
        safety_signal_type=safety_signal_type.value if safety_signal_type else None,
        safety_term="QT prolongation" if safety_signal_type else None,
        safety_severity=safety_severity.value if safety_severity else None,
        safety_status=safety_status.value if safety_status else None,
        safety_identified_at=datetime(2026, 2, decision_day - 2, tzinfo=UTC) if safety_signal_type else None,
        safety_confirmed_at=datetime(2026, 2, decision_day, tzinfo=UTC) if safety_signal_type else None,
        affected_population="Patients with cardiac risk factors" if safety_signal_type else None,
        risk_actions=["ECG monitoring"] if safety_signal_type else [],
        source_updated_at=datetime(2026, 3, 1, tzinfo=UTC),
        indication_entity_id=indication.id if indication else None,
        organization_entity_id=organization.id if organization else None,
        details={"review_pathway": "priority"},
    )
    session.add(event)
    session.flush()
    return event


def test_regulatory_search_filters_facets_links_and_tenant_isolation(session: Session, tenant: Tenant) -> None:
    subject = _entity(session, tenant, EntityType.DRUG, "VX-101")
    indication = _entity(session, tenant, EntityType.DISEASE, "EGFR-positive NSCLC")
    sponsor = _entity(session, tenant, EntityType.ORGANIZATION, "Acme Pharma")
    event = _event(
        session,
        tenant,
        subject,
        identifier="FDA-2026-001",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=20,
        indication=indication,
        organization=sponsor,
        designation_type=RegulatoryDesignationType.BREAKTHROUGH_THERAPY,
        label_change_type=RegulatoryLabelChangeType.INITIAL_LABEL,
        label_version="USPI-2026-02",
        has_boxed_warning=True,
        safety_signal_type=RegulatorySafetySignalType.ADVERSE_EVENT,
        safety_severity=RegulatorySafetySeverity.SERIOUS,
        safety_status=RegulatorySafetyStatus.CONFIRMED,
    )
    negative_event = _event(
        session,
        tenant,
        subject,
        identifier="FDA-2026-002",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=22,
        indication=indication,
        organization=sponsor,
        designation_type=RegulatoryDesignationType.BREAKTHROUGH_THERAPY,
        label_change_type=RegulatoryLabelChangeType.INITIAL_LABEL,
        label_version="USPI-2026-03",
        has_boxed_warning=True,
        safety_signal_type=RegulatorySafetySignalType.ADVERSE_EVENT,
        safety_severity=RegulatorySafetySeverity.SERIOUS,
        safety_status=RegulatorySafetyStatus.MONITORING,
    )
    _event(
        session,
        tenant,
        subject,
        identifier="EMA-2026-001",
        agency="EMA",
        jurisdiction="EU",
        event_type="submission",
        status="under_review",
        decision_day=10,
    )
    other_tenant = Tenant(slug="other-regulatory", name="Other Regulatory Tenant")
    session.add(other_tenant)
    session.flush()
    hidden_subject = _entity(session, other_tenant, EntityType.DRUG, "Hidden VX-101")
    _event(
        session,
        other_tenant,
        hidden_subject,
        identifier="FDA-2026-999",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=25,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_regulatory_events(
        "Acme Pharma",
        "FDA",
        "US",
        "approval",
        "approved",
        100,
        0,
        designation_type=RegulatoryDesignationType.BREAKTHROUGH_THERAPY.value,
        label_change_type=RegulatoryLabelChangeType.INITIAL_LABEL.value,
        has_boxed_warning=True,
        safety_signal_type=RegulatorySafetySignalType.ADVERSE_EVENT.value,
        safety_severity=RegulatorySafetySeverity.SERIOUS.value,
        safety_status=RegulatorySafetyStatus.CONFIRMED.value,
        decision_from=datetime(2026, 2, 1, tzinfo=UTC),
        decision_to=datetime(2026, 2, 28, tzinfo=UTC),
        source_updated_from=datetime(2026, 3, 1, tzinfo=UTC),
        source_updated_to=datetime(2026, 3, 31, tzinfo=UTC),
    )

    assert result.total == 1
    assert result.facets == {
        "agency": {"FDA": 1},
        "jurisdiction": {"US": 1},
        "event_type": {"approval": 1},
        "status": {"approved": 1},
        "designation_type": {"breakthrough_therapy": 1},
        "label_change_type": {"initial_label": 1},
        "has_boxed_warning": {"true": 1},
        "safety_signal_type": {"adverse_event": 1},
        "safety_severity": {"serious": 1},
        "safety_status": {"confirmed": 1},
    }
    assert result.query_schema_version == "pharma.regulatory.search.v4"
    assert result.sort_by == "decision_date"
    assert result.sort_direction == "desc"
    applied = {item.field: item.value for item in result.applied_filters}
    assert applied["designation_type"] == "breakthrough_therapy"
    assert applied["has_boxed_warning"] is True
    assert applied["safety_status"] == "confirmed"
    assert result.items[0].id == event.id
    assert negative_event.id not in {item.id for item in result.items}
    assert (result.items[0].subject_entity.entity_type.value, result.items[0].subject_entity.name) == (
        "drug",
        "VX-101",
    )
    assert result.items[0].indication_entity is not None
    assert result.items[0].indication_entity.name == "EGFR-positive NSCLC"
    assert result.items[0].organization_entity is not None
    assert result.items[0].organization_entity.name == "Acme Pharma"
    assert result.items[0].label_change_type == RegulatoryLabelChangeType.INITIAL_LABEL
    assert result.items[0].label_version == "USPI-2026-02"
    assert result.items[0].approved_population == "Adults with EGFR exon 19 deletion"
    assert result.items[0].has_boxed_warning is True
    assert result.items[0].safety_term == "QT prolongation"
    assert result.items[0].risk_actions == ["ECG monitoring"]
    assert result.warnings == ["未观察到监管事件不代表不存在；结果受监管辖区、数据授权、更新时效和治理状态限制。"]
    detail = IntelligenceService(session, tenant.id).regulatory_event_detail(event.id)
    assert detail is not None
    assert detail.id == event.id
    assert detail.subject_entity.name == "VX-101"
    assert IntelligenceService(session, other_tenant.id).regulatory_event_detail(event.id) is None


def test_regulatory_search_escapes_wildcards_and_paginates_deterministically(
    session: Session,
    tenant: Tenant,
) -> None:
    subject = _entity(session, tenant, EntityType.DRUG, "VX-202")
    _event(
        session,
        tenant,
        subject,
        identifier="FDA-2026-010",
        agency="FDA",
        jurisdiction="US",
        event_type="submission",
        status="under_review",
        decision_day=1,
    )
    _event(
        session,
        tenant,
        subject,
        identifier="FDA-2026-011",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=2,
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_regulatory_events("%", None, None, None, None, 100, 0).total == 0
    by_subject = service.search_regulatory_events("VX-202", None, None, None, None, 100, 0)
    assert by_subject.total == 2
    by_entity = service.search_regulatory_events(None, None, None, None, None, 100, 0, entity_id=subject.id)
    assert by_entity.total == 2
    first = service.search_regulatory_events(None, None, None, None, None, 1, 0)
    second = service.search_regulatory_events(None, None, None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].event_identifier == "FDA-2026-011"
    assert second.items[0].event_identifier == "FDA-2026-010"


def test_regulatory_search_sorts_full_result_set_by_subject_name(session: Session, tenant: Tenant) -> None:
    zeta = _entity(session, tenant, EntityType.DRUG, "Zeta drug")
    alpha = _entity(session, tenant, EntityType.DRUG, "Alpha drug")
    zeta_event = _event(
        session,
        tenant,
        zeta,
        identifier="FDA-ZETA",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=1,
    )
    alpha_event = _event(
        session,
        tenant,
        alpha,
        identifier="FDA-ALPHA",
        agency="FDA",
        jurisdiction="US",
        event_type="submission",
        status="under_review",
        decision_day=2,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_regulatory_events(
        None,
        None,
        None,
        None,
        None,
        1,
        0,
        sort_by="subject",
        sort_direction="asc",
    )

    assert result.total == 2
    assert result.items[0].id == alpha_event.id
    assert result.items[0].id != zeta_event.id
    assert result.sort_by == "subject"
    assert result.sort_direction == "asc"
    multi_sorted = IntelligenceService(session, tenant.id).search_regulatory_events(
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(SortClause(field="agency", direction="asc"), SortClause(field="subject", direction="desc")),
    )
    assert [item.id for item in multi_sorted.items] == [zeta_event.id, alpha_event.id]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "agency", "direction": "asc"},
        {"field": "subject", "direction": "desc"},
    ]


def test_regulatory_landscape_aggregates_full_hit_set_not_current_page(session: Session, tenant: Tenant) -> None:
    """Landscape buckets must come from the complete filtered set, not the returned page."""

    subject = _entity(session, tenant, EntityType.DRUG, "VX-REG-1")
    _event(
        session,
        tenant,
        subject,
        identifier="REG-L1",
        agency="FDA",
        jurisdiction="US",
        event_type="approval",
        status="approved",
        decision_day=1,
    )
    _event(
        session,
        tenant,
        subject,
        identifier="REG-L2",
        agency="FDA",
        jurisdiction="US",
        event_type="submission",
        status="submitted",
        decision_day=2,
    )
    _event(
        session,
        tenant,
        subject,
        identifier="REG-L3",
        agency="EMA",
        jurisdiction="EU",
        event_type="approval",
        status="approved",
        decision_day=3,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_regulatory_events(None, None, None, None, None, 1, 0)

    assert len(result.items) == 1
    landscape = result.landscape
    assert landscape.total_events == 3
    assert {(bucket.key, bucket.count) for bucket in landscape.event_type} == {("approval", 2), ("submission", 1)}
    assert {(bucket.key, bucket.count) for bucket in landscape.agency} == {("FDA", 2), ("EMA", 1)}
    assert sum(bucket.count for bucket in landscape.decision_year) == 3
    assert abs(sum(bucket.share for bucket in landscape.event_type) - 1.0) < 1e-9

    filtered = IntelligenceService(session, tenant.id).search_regulatory_events(None, "EMA", None, None, None, 25, 0)
    assert filtered.landscape.total_events == 1
    assert [bucket.key for bucket in filtered.landscape.event_type] == ["approval"]
