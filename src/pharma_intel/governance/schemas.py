from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, JsonValue, model_validator

from pharma_intel.models import (
    DealDirection,
    DealPartyRole,
    DealRightType,
    DealStatus,
    EntityType,
    ProgramTargetRole,
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    TrialEntityRole,
    TrialResultDisclosureType,
    TrialResultEvaluation,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    quote: str = Field(min_length=3, max_length=4000)
    locator: str | None = Field(default=None, max_length=500)
    confidence: float = Field(ge=0, le=1)


class EntityReference(StrictModel):
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=500)
    external_ids: dict[str, str] = Field(default_factory=dict)


class ClaimFact(StrictModel):
    fact_kind: Literal["claim"]
    subject: EntityReference
    predicate: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    object_entity: EntityReference | None = None
    value: dict[str, Any] | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    citation: Citation

    @model_validator(mode="after")
    def exactly_one_object(self) -> ClaimFact:
        if (self.object_entity is None) == (self.value is None):
            raise ValueError("Exactly one of object_entity or value is required")
        return self


class TargetProfileFact(StrictModel):
    fact_kind: Literal["target_profile"]
    subject: EntityReference
    gene_symbol: str | None = Field(default=None, max_length=80)
    uniprot_accession: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6,10}$")
    organism: str | None = Field(default=None, max_length=120)
    target_class: str | None = Field(default=None, max_length=160)
    sequence: str | None = Field(default=None, min_length=1, max_length=200_000, pattern=r"^[A-Za-z*\s]+$")
    function_summary: str | None = Field(default=None, max_length=8000)
    citation: Citation


class TargetEvidenceFact(StrictModel):
    fact_kind: Literal["target_evidence"]
    record_identifier: str = Field(min_length=1, max_length=240)
    target: EntityReference
    disease: EntityReference | None = None
    evidence_type: Literal[
        "genetic_association",
        "expression",
        "functional",
        "translational",
        "biomarker",
        "safety",
    ]
    direction: Literal["supports", "opposes", "neutral", "unknown"]
    study_name: str | None = Field(default=None, max_length=500)
    population: str | None = Field(default=None, max_length=500)
    tissue: str | None = Field(default=None, max_length=240)
    variant: str | None = Field(default=None, max_length=240)
    effect_size: float | None = None
    effect_unit: str | None = Field(default=None, max_length=80)
    p_value: float | None = Field(default=None, ge=0, le=1)
    sample_size: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=1, max_length=8000)
    observed_at: datetime | None = None
    qualifiers: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=50)
    citation: Citation


class StructureFact(StrictModel):
    fact_kind: Literal["structure"]
    subject: EntityReference
    canonical_smiles: str = Field(min_length=1, max_length=20_000)
    standard_inchi: str | None = Field(default=None, max_length=40_000)
    standard_inchi_key: str | None = Field(default=None, pattern=r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
    molecular_formula: str | None = Field(default=None, max_length=200)
    citation: Citation


class ActivityFact(StrictModel):
    fact_kind: Literal["activity"]
    compound: EntityReference
    target: EntityReference
    assay_name: str = Field(min_length=1, max_length=500)
    assay_type: str | None = Field(default=None, max_length=80)
    reported_type: str = Field(min_length=1, max_length=80)
    reported_relation: Literal["=", "<", "<=", ">", ">=", "~"]
    reported_value: str = Field(min_length=1, max_length=120)
    reported_units: str | None = Field(default=None, max_length=40)
    standard_value: float | None = None
    standard_units: str | None = Field(default=None, max_length=40)
    citation: Citation


class ProgramStatusHistoryFact(StrictModel):
    phase: str = Field(min_length=1, max_length=80)
    status: str | None = Field(default=None, max_length=120)
    program_status: Literal["active", "inactive", "unknown"] | None = None
    effective_at: datetime
    geography: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=2000)


class ProgramMilestoneFact(StrictModel):
    milestone_type: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    occurred_at: datetime
    geography: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)


class ProgramOrganizationFact(StrictModel):
    role: Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"]
    entity: EntityReference
    country_region: str | None = Field(default=None, max_length=120)
    organization_type: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_organization_type(self) -> ProgramOrganizationFact:
        if self.entity.entity_type != EntityType.ORGANIZATION:
            raise ValueError("Program organization facts must reference an organization entity")
        return self


class ProgramTargetFact(StrictModel):
    role: ProgramTargetRole
    entity: EntityReference

    @model_validator(mode="after")
    def validate_target_type(self) -> ProgramTargetFact:
        if self.entity.entity_type != EntityType.TARGET:
            raise ValueError("program targets must reference target entities")
        return self


class ProgramFact(StrictModel):
    fact_kind: Literal["program"]
    drug: EntityReference
    target: EntityReference | None = None
    targets: list[ProgramTargetFact] = Field(default_factory=list, max_length=20)
    indication: EntityReference | None = None
    organization: EntityReference | None = None
    organizations: list[ProgramOrganizationFact] = Field(default_factory=list, max_length=20)
    phase: str = Field(min_length=1, max_length=80)
    status: str | None = Field(default=None, max_length=120)
    status_date: datetime | None = None
    modality: str | None = Field(default=None, max_length=160)
    innovation_type: str | None = Field(default=None, max_length=120)
    therapeutic_area: str | None = Field(default=None, max_length=120)
    drug_category: str | None = Field(default=None, max_length=120)
    mechanism_of_action: str | None = Field(default=None, max_length=500)
    geography: str | None = Field(default=None, max_length=120)
    global_phase: str | None = Field(default=None, min_length=1, max_length=80)
    china_phase: str | None = Field(default=None, min_length=1, max_length=80)
    global_phase_started_at: datetime | None = None
    china_phase_started_at: datetime | None = None
    development_rights_regions: list[str] = Field(default_factory=list, max_length=100)
    commercialization_rights_regions: list[str] = Field(default_factory=list, max_length=100)
    program_tags: list[str] = Field(default_factory=list, max_length=100)
    status_history: list[ProgramStatusHistoryFact] = Field(default_factory=list, max_length=500)
    milestones: list[ProgramMilestoneFact] = Field(default_factory=list, max_length=500)
    citation: Citation

    @model_validator(mode="after")
    def validate_regional_phase_dates(self) -> ProgramFact:
        if self.global_phase_started_at is not None and self.global_phase is None:
            raise ValueError("global_phase_started_at requires global_phase")
        if self.china_phase_started_at is not None and self.china_phase is None:
            raise ValueError("china_phase_started_at requires china_phase")
        if self.target is not None and self.targets:
            raise ValueError("target and targets cannot both be provided")
        if self.targets:
            primary_count = sum(item.role == ProgramTargetRole.PRIMARY for item in self.targets)
            if primary_count != 1:
                raise ValueError("targets must contain exactly one primary target")
            identities = [
                (
                    item.entity.entity_type.value,
                    item.entity.name.strip().casefold(),
                    tuple(sorted(item.entity.external_ids.items())),
                )
                for item in self.targets
            ]
            if len(identities) != len(set(identities)):
                raise ValueError("targets must not contain duplicate entities")
        if self.organization is not None and self.organization.entity_type != EntityType.ORGANIZATION:
            raise ValueError("organization must reference an organization entity")
        if self.organizations:
            organization_identities = [
                (
                    item.entity.entity_type.value,
                    item.entity.name.strip().casefold(),
                    tuple(sorted(item.entity.external_ids.items())),
                )
                for item in self.organizations
            ]
            if len(organization_identities) != len(set(organization_identities)):
                raise ValueError("organizations must not contain duplicate entities")
            originators = [item for item in self.organizations if item.role == "originator"]
            if len(originators) > 1:
                raise ValueError("organizations must not contain more than one originator")
            if self.organization is not None and originators:
                legacy_identity = (
                    self.organization.entity_type.value,
                    self.organization.name.strip().casefold(),
                    tuple(sorted(self.organization.external_ids.items())),
                )
                if organization_identities[self.organizations.index(originators[0])] != legacy_identity:
                    raise ValueError("organization must match the originator in organizations")
        for field_name in (
            "development_rights_regions",
            "commercialization_rights_regions",
            "program_tags",
        ):
            values = getattr(self, field_name)
            normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
            if any(len(value) > 240 for value in normalized):
                raise ValueError(f"{field_name} values must not exceed 240 characters")
            setattr(self, field_name, normalized)
        return self


class TrialInterventionFact(StrictModel):
    name: str = Field(min_length=1, max_length=500)
    type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=8000)
    arm_labels: list[str] = Field(default_factory=list, max_length=100)
    other_names: list[str] = Field(default_factory=list, max_length=100)


class TrialEntityRoleFact(StrictModel):
    role: TrialEntityRole
    entity: EntityReference

    @model_validator(mode="after")
    def validate_entity_type(self) -> TrialEntityRoleFact:
        expected_type = EntityType.DRUG if self.role.value.endswith("_drug") else EntityType.TARGET
        if self.entity.entity_type is not expected_type:
            raise ValueError(f"{self.role.value} requires an entity of type {expected_type.value}")
        return self


class TrialResultDisclosureFact(StrictModel):
    disclosure_key: str = Field(min_length=1, max_length=240)
    version: int = Field(ge=1, le=10_000)
    disclosure_type: TrialResultDisclosureType
    external_id: str | None = Field(default=None, max_length=240)
    title: str = Field(min_length=1, max_length=4000)
    disclosed_at: datetime
    conference_name: str | None = Field(default=None, max_length=500)
    is_key_result: bool = False
    result_evaluation: TrialResultEvaluation | None = None
    citation: Citation

    @model_validator(mode="after")
    def validate_conference_context(self) -> TrialResultDisclosureFact:
        if (
            self.disclosure_type
            in {
                TrialResultDisclosureType.CONFERENCE_ABSTRACT,
                TrialResultDisclosureType.CONFERENCE_PRESENTATION,
                TrialResultDisclosureType.POSTER,
            }
            and not self.conference_name
        ):
            raise ValueError("conference_name is required for conference and poster disclosures")
        return self


class TrialSponsorFact(StrictModel):
    name: str = Field(min_length=1, max_length=500)
    sponsor_class: str | None = Field(default=None, max_length=120)


class TrialLocationFact(StrictModel):
    facility: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=160)
    state: str | None = Field(default=None, max_length=160)
    country: str = Field(min_length=1, max_length=160)
    status: str | None = Field(default=None, max_length=120)


class TrialDesignFact(StrictModel):
    allocation: str | None = Field(default=None, max_length=120)
    intervention_model: str | None = Field(default=None, max_length=160)
    intervention_model_description: str | None = Field(default=None, max_length=4000)
    primary_purpose: str | None = Field(default=None, max_length=160)
    observational_model: str | None = Field(default=None, max_length=160)
    time_perspective: str | None = Field(default=None, max_length=160)
    masking: str | None = Field(default=None, max_length=120)
    masking_description: str | None = Field(default=None, max_length=4000)
    who_masked: list[str] = Field(default_factory=list, max_length=20)


class TrialEligibilityFact(StrictModel):
    minimum_age: str | None = Field(default=None, max_length=80)
    maximum_age: str | None = Field(default=None, max_length=80)
    sex: str | None = Field(default=None, max_length=80)
    gender_based: bool | None = None
    healthy_volunteers: bool | None = None
    sampling_method: str | None = Field(default=None, max_length=160)
    criteria: str | None = Field(default=None, max_length=20_000)


class TrialArmFact(StrictModel):
    label: str = Field(min_length=1, max_length=500)
    type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=8000)
    intervention_names: list[str] = Field(default_factory=list, max_length=100)


class TrialOutcomeResultFact(StrictModel):
    group_label: str = Field(min_length=1, max_length=500)
    value: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=120)
    participants: int | None = Field(default=None, ge=0)
    dispersion: str | None = Field(default=None, max_length=240)
    lower_limit: float | None = None
    upper_limit: float | None = None


class TrialStatisticalAnalysisFact(StrictModel):
    method: str | None = Field(default=None, max_length=500)
    p_value: str | None = Field(default=None, max_length=120)
    parameter_type: str | None = Field(default=None, max_length=160)
    parameter_value: float | None = None
    confidence_interval_percent: float | None = Field(default=None, ge=0, le=100)
    lower_limit: float | None = None
    upper_limit: float | None = None
    notes: str | None = Field(default=None, max_length=4000)


class TrialOutcomeFact(StrictModel):
    outcome_type: Literal["PRIMARY", "SECONDARY", "OTHER_PRE_SPECIFIED", "POST_HOC", "OTHER"]
    measure: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=8000)
    time_frame: str | None = Field(default=None, max_length=1000)
    results: list[TrialOutcomeResultFact] = Field(default_factory=list, max_length=500)
    statistical_analyses: list[TrialStatisticalAnalysisFact] = Field(default_factory=list, max_length=100)


class TrialStatusHistoryFact(StrictModel):
    status: str = Field(min_length=1, max_length=120)
    effective_at: datetime
    effective_at_precision: Literal["day", "month", "year"] | None = None
    reason: str | None = Field(default=None, max_length=4000)


class TrialFact(StrictModel):
    fact_kind: Literal["trial"]
    trial: EntityReference
    registry_name: str = Field(min_length=1, max_length=80)
    registry_id: str = Field(min_length=1, max_length=160)
    official_title: str = Field(min_length=1, max_length=2000)
    acronym: str | None = Field(default=None, min_length=1, max_length=240)
    initiation_type: Literal["iit", "ist"] | None = None
    therapy_lines: list[
        Literal[
            "first_line",
            "second_line",
            "third_or_later",
            "prevention",
            "treatment_naive",
            "add_on",
            "adjuvant",
            "neoadjuvant",
            "maintenance",
            "consolidation",
            "induction",
            "conversion",
        ]
    ] = Field(default_factory=list, max_length=12)
    overall_status: str | None = Field(default=None, max_length=120)
    phases: list[str] = Field(default_factory=list, max_length=20)
    study_type: str | None = Field(default=None, max_length=120)
    enrollment: int | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    start_date_precision: Literal["day", "month", "year"] | None = None
    completion_date: datetime | None = None
    completion_date_precision: Literal["day", "month", "year"] | None = None
    conditions: list[str] = Field(default_factory=list, max_length=100)
    interventions: list[TrialInterventionFact] = Field(default_factory=list, max_length=100)
    entity_roles: list[TrialEntityRoleFact] = Field(default_factory=list, max_length=200)
    sponsors: list[TrialSponsorFact] = Field(default_factory=list, max_length=100)
    locations: list[TrialLocationFact] = Field(default_factory=list, max_length=2000)
    study_design: TrialDesignFact = Field(default_factory=TrialDesignFact)
    eligibility: TrialEligibilityFact = Field(default_factory=TrialEligibilityFact)
    arms: list[TrialArmFact] = Field(default_factory=list, max_length=100)
    outcomes: list[TrialOutcomeFact] = Field(default_factory=list, max_length=500)
    status_history: list[TrialStatusHistoryFact] = Field(default_factory=list, max_length=500)
    result_evaluation: TrialResultEvaluation | None = None
    result_disclosures: list[TrialResultDisclosureFact] = Field(default_factory=list, max_length=1000)
    results_first_posted: datetime | None = None
    last_update_posted: datetime | None = None
    linked_entities: list[EntityReference] = Field(default_factory=list, max_length=200)
    citation: Citation


class PatentPublicationFact(StrictModel):
    publication_number: str = Field(min_length=1, max_length=160)
    application_number: str | None = Field(default=None, max_length=160)
    jurisdiction: str | None = Field(default=None, max_length=80)
    publication_date: datetime | None = None
    grant_date: datetime | None = None


class PatentLegalEventFact(StrictModel):
    event_type: str = Field(min_length=1, max_length=120)
    status: str | None = Field(default=None, max_length=120)
    occurred_at: datetime
    jurisdiction: str | None = Field(default=None, max_length=80)
    publication_number: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)


class PatentClaimFact(StrictModel):
    claim_number: str = Field(min_length=1, max_length=40)
    claim_type: Literal["composition", "method", "use", "formulation", "sequence", "other"]
    summary: str = Field(min_length=1, max_length=4000)
    scope: str | None = Field(default=None, max_length=4000)


class PatentFact(StrictModel):
    fact_kind: Literal["patent"]
    patent: EntityReference
    family_identifier: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=2000)
    priority_date: datetime | None = None
    applicants: list[str] = Field(default_factory=list, max_length=100)
    inventors: list[str] = Field(default_factory=list, max_length=200)
    publications: list[PatentPublicationFact | str] = Field(default_factory=list, max_length=500)
    legal_status: str | None = Field(default=None, max_length=120)
    legal_status_at: datetime | None = None
    legal_events: list[PatentLegalEventFact] = Field(default_factory=list, max_length=1000)
    independent_claims: list[PatentClaimFact] = Field(default_factory=list, max_length=100)
    expiration_date: datetime | None = None
    linked_entities: list[EntityReference] = Field(default_factory=list, max_length=100)
    citation: Citation


class DealPartyRoleFact(StrictModel):
    party: EntityReference
    role: DealPartyRole
    country_region: str | None = Field(default=None, max_length=120)
    organization_type: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_organization(self) -> DealPartyRoleFact:
        if self.party.entity_type != EntityType.ORGANIZATION:
            raise ValueError("Deal party roles require an organization entity")
        return self


class DealAssetStageFact(StrictModel):
    asset: EntityReference
    development_phase_at_transaction: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_asset(self) -> DealAssetStageFact:
        if self.asset.entity_type not in {EntityType.DRUG, EntityType.PRODUCT, EntityType.TECHNOLOGY}:
            raise ValueError("Deal assets must be drug, product, or technology entities")
        if self.development_phase_at_transaction is not None:
            self.development_phase_at_transaction = self.development_phase_at_transaction.strip().lower()
            valid_phases = {
                "discovery",
                "preclinical",
                "ind",
                "phase_1",
                "phase_1_2",
                "phase_2",
                "phase_2_3",
                "phase_3",
                "filed",
                "approved",
                "discontinued",
            }
            if self.development_phase_at_transaction not in valid_phases:
                raise ValueError("Unsupported development phase at transaction")
        return self


class DealRightFact(StrictModel):
    holder: EntityReference
    right_type: DealRightType
    territory: str = Field(min_length=1, max_length=240)
    exclusive: bool | None = None
    scope_description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_holder(self) -> DealRightFact:
        if self.holder.entity_type != EntityType.ORGANIZATION:
            raise ValueError("Deal rights require an organization holder")
        return self


class DealFact(StrictModel):
    fact_kind: Literal["deal"]
    deal: EntityReference
    deal_type: str = Field(min_length=1, max_length=100)
    parties: list[EntityReference] = Field(default_factory=list, max_length=50)
    party_roles: list[DealPartyRoleFact] = Field(default_factory=list, max_length=50)
    assets: list[EntityReference] = Field(default_factory=list, max_length=100)
    asset_stages: list[DealAssetStageFact] = Field(default_factory=list, max_length=100)
    rights: list[DealRightFact] = Field(default_factory=list, max_length=200)
    status: DealStatus = DealStatus.UNKNOWN
    direction: DealDirection = DealDirection.UNDISCLOSED
    direction_reference_jurisdiction: str | None = Field(default=None, max_length=120)
    announced_at: datetime | None = None
    terminated_at: datetime | None = None
    source_updated_at: datetime | None = None
    territory: str | None = Field(default=None, max_length=240)
    upfront_amount: float | None = Field(default=None, ge=0)
    total_potential_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    terms: dict[str, Any] = Field(default_factory=dict, max_length=100)
    citation: Citation

    @model_validator(mode="after")
    def validate_deal_semantics(self) -> DealFact:
        party_keys = {(party.entity_type.value, party.name.casefold()) for party in self.parties} | {
            (association.party.entity_type.value, association.party.name.casefold()) for association in self.party_roles
        }
        if len(party_keys) < 2:
            raise ValueError("A deal requires at least two distinct parties")
        if (
            self.direction in {DealDirection.INBOUND, DealDirection.OUTBOUND}
            and not self.direction_reference_jurisdiction
        ):
            raise ValueError("Inbound and outbound deals require a reference jurisdiction")
        if self.terminated_at and self.announced_at and self.terminated_at < self.announced_at:
            raise ValueError("Deal termination cannot precede announcement")
        if (self.upfront_amount is not None or self.total_potential_amount is not None) and self.currency is None:
            raise ValueError("Deal amounts require an ISO currency")
        party_names = {name for _entity_type, name in party_keys}
        if any(right.holder.name.casefold() not in party_names for right in self.rights):
            raise ValueError("Every right holder must also be a deal party")
        return self


class RegulatoryFact(StrictModel):
    fact_kind: Literal["regulatory"]
    subject: EntityReference
    agency: str = Field(min_length=2, max_length=80)
    jurisdiction: str = Field(min_length=2, max_length=120)
    event_identifier: str = Field(min_length=2, max_length=160)
    application_number: str | None = Field(default=None, max_length=120)
    event_type: Literal[
        "submission",
        "acceptance",
        "priority_review",
        "approval",
        "conditional_approval",
        "designation",
        "label_update",
        "safety_signal",
        "safety_communication",
        "rejection",
        "withdrawal",
        "suspension",
        "other",
    ]
    status: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=3, max_length=2000)
    decision_date: datetime | None = None
    designation_type: RegulatoryDesignationType | None = None
    label_change_type: RegulatoryLabelChangeType | None = None
    label_version: str | None = Field(default=None, max_length=160)
    label_effective_at: datetime | None = None
    approved_population: str | None = Field(default=None, max_length=4000)
    line_of_therapy: str | None = Field(default=None, max_length=240)
    biomarker: str | None = Field(default=None, max_length=240)
    route_of_administration: str | None = Field(default=None, max_length=160)
    dosage_form: str | None = Field(default=None, max_length=160)
    has_boxed_warning: bool | None = None
    safety_signal_type: RegulatorySafetySignalType | None = None
    safety_term: str | None = Field(default=None, max_length=500)
    safety_severity: RegulatorySafetySeverity | None = None
    safety_status: RegulatorySafetyStatus | None = None
    safety_identified_at: datetime | None = None
    safety_confirmed_at: datetime | None = None
    safety_resolved_at: datetime | None = None
    affected_population: str | None = Field(default=None, max_length=4000)
    risk_actions: list[str] = Field(default_factory=list, max_length=50)
    source_updated_at: datetime | None = None
    indication: EntityReference | None = None
    organization: EntityReference | None = None
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=50)
    citation: Citation

    @model_validator(mode="after")
    def validate_regulatory_semantics(self) -> RegulatoryFact:
        if self.safety_confirmed_at and self.safety_identified_at:
            if self.safety_confirmed_at < self.safety_identified_at:
                raise ValueError("Safety signal confirmation cannot precede identification")
        if self.safety_resolved_at and self.safety_identified_at:
            if self.safety_resolved_at < self.safety_identified_at:
                raise ValueError("Safety signal resolution cannot precede identification")
        if self.label_effective_at and self.decision_date and self.label_effective_at < self.decision_date:
            raise ValueError("Label effective date cannot precede its regulatory decision")
        if self.designation_type and self.event_type not in {
            "designation",
            "priority_review",
            "approval",
            "conditional_approval",
        }:
            raise ValueError("Designation type is incompatible with the regulatory event type")
        label_fields_present = any(
            value is not None
            for value in (
                self.label_change_type,
                self.label_version,
                self.label_effective_at,
                self.approved_population,
                self.line_of_therapy,
                self.biomarker,
                self.route_of_administration,
                self.dosage_form,
                self.has_boxed_warning,
            )
        )
        if label_fields_present and self.event_type not in {"approval", "conditional_approval", "label_update"}:
            raise ValueError("Label fields are incompatible with the regulatory event type")
        safety_fields_present = bool(self.risk_actions) or any(
            value is not None
            for value in (
                self.safety_signal_type,
                self.safety_term,
                self.safety_severity,
                self.safety_status,
                self.safety_identified_at,
                self.safety_confirmed_at,
                self.safety_resolved_at,
                self.affected_population,
            )
        )
        if safety_fields_present and self.event_type not in {
            "approval",
            "conditional_approval",
            "label_update",
            "safety_signal",
            "safety_communication",
            "withdrawal",
            "suspension",
        }:
            raise ValueError("Safety fields are incompatible with the regulatory event type")
        return self


class PatientPopulationReference(StrictModel):
    population_key: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    targets: list[EntityReference] = Field(default_factory=list, max_length=50)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_targets(self) -> PatientPopulationReference:
        if any(target.entity_type != EntityType.TARGET for target in self.targets):
            raise ValueError("Patient population targets must reference target entities")
        return self


class EpidemiologyFact(StrictModel):
    fact_kind: Literal["epidemiology"]
    observation_identifier: str = Field(min_length=2, max_length=200)
    disease: EntityReference
    measure: Literal[
        "prevalence",
        "incidence",
        "mortality",
        "patient_count",
        "diagnosed_count",
        "treated_count",
        "survival_rate",
        "daly",
        "other",
    ]
    value: float = Field(ge=0)
    lower_bound: float | None = Field(default=None, ge=0)
    upper_bound: float | None = Field(default=None, ge=0)
    unit: str = Field(min_length=1, max_length=120)
    geography: str = Field(min_length=1, max_length=160)
    population_scope: str = Field(min_length=1, max_length=500)
    patient_population: PatientPopulationReference | None = None
    age_group: str | None = Field(default=None, max_length=120)
    sex: str | None = Field(default=None, max_length=80)
    period_start: datetime | None = None
    period_end: datetime | None = None
    sample_size: int | None = Field(default=None, ge=1)
    methodology: str | None = Field(default=None, max_length=8000)
    publisher: EntityReference | None = None
    citation: Citation

    @model_validator(mode="after")
    def validate_epidemiology_dimensions(self) -> EpidemiologyFact:
        if self.disease.entity_type != EntityType.DISEASE:
            raise ValueError("Epidemiology disease must reference a disease entity")
        if self.publisher is not None and self.publisher.entity_type != EntityType.ORGANIZATION:
            raise ValueError("Epidemiology publisher must reference an organization entity")
        if self.lower_bound is not None and self.lower_bound > self.value:
            raise ValueError("Epidemiology lower bound must not exceed value")
        if self.upper_bound is not None and self.upper_bound < self.value:
            raise ValueError("Epidemiology upper bound must not be below value")
        if self.period_start is not None and self.period_end is not None and self.period_end < self.period_start:
            raise ValueError("Epidemiology period end must not precede period start")
        return self


class NewsFact(StrictModel):
    fact_kind: Literal["news"]
    event_identifier: str = Field(min_length=2, max_length=240)
    event_type: Literal[
        "news",
        "press_release",
        "corporate_announcement",
        "publication",
        "conference_abstract",
        "poster",
        "presentation",
        "other",
    ]
    title: str = Field(min_length=3, max_length=2000)
    summary: str | None = Field(default=None, max_length=8000)
    published_at: datetime | None = None
    language: str | None = Field(default=None, max_length=32)
    publisher: EntityReference | None = None
    related_entities: list[EntityReference] = Field(default_factory=list, max_length=200)
    canonical_url: AnyHttpUrl | None = None
    venue: str | None = Field(default=None, max_length=240)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=50)
    citation: Citation

    @model_validator(mode="after")
    def validate_news_entities(self) -> NewsFact:
        if self.publisher is not None and self.publisher.entity_type != EntityType.ORGANIZATION:
            raise ValueError("News publisher must reference an organization entity")
        return self


ExtractedFact = Annotated[
    ClaimFact
    | TargetProfileFact
    | TargetEvidenceFact
    | StructureFact
    | ActivityFact
    | ProgramFact
    | TrialFact
    | PatentFact
    | DealFact
    | RegulatoryFact
    | EpidemiologyFact
    | NewsFact,
    Field(discriminator="fact_kind"),
]


class ExtractionEnvelope(StrictModel):
    document_type: str = Field(min_length=1, max_length=120)
    document_summary: str = Field(max_length=8000)
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=100)
