from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.chemistry.standardization import STANDARDIZATION_VERSION
from pharma_intel.governance.chembl_enrichment import (
    ChemblActivity,
    ChemblActivityCoverage,
    ChemblStructure,
    enrichment_facts,
)
from pharma_intel.governance.chembl_names import name_facts
from pharma_intel.governance.contracts import OFFICIAL_SOURCE_UPDATE_POLICY
from pharma_intel.governance.schemas import (
    ActivityFact,
    Citation,
    EntityAliasFact,
    EntityReference,
    ProgramFact,
    ProgramTargetFact,
    StructureFact,
    TargetProfileFact,
)
from pharma_intel.models import (
    DevelopmentProgram,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    ProgramTargetRole,
    ReviewStatus,
)
from pharma_intel.program_semantics import (
    CHEMBL_MAXIMUM_PHASES,
    chembl_maximum_phase,
    chembl_reported_phase_number,
    public_program_drug_category,
    public_program_modality,
)

ADAPTER_NAME = "chembl_mechanism_json"
ADAPTER_VERSION = "1.4.0"
SNAPSHOT_SCHEMA = "pharma.chembl.mechanism.v3"

AliasName = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]


class _SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChemblTarget(_SnapshotModel):
    chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    pref_name: str = Field(min_length=1, max_length=500)
    target_type: str | None = Field(default=None, max_length=120)
    organism: str | None = Field(default=None, max_length=160)
    gene_symbol: str | None = Field(default=None, max_length=80)
    uniprot_accession: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6,10}$")
    aliases: list[AliasName] = Field(default_factory=list, max_length=200)


class _PhasedSnapshotModel(_SnapshotModel):
    max_phase: float | None = Field(default=None, ge=-1, le=4, strict=True)

    @field_validator("max_phase", mode="before")
    @classmethod
    def decode_reported_phase(cls, value: object) -> float | None:
        return chembl_reported_phase_number(value)


class ChemblMolecule(_PhasedSnapshotModel):
    chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    pref_name: str = Field(min_length=1, max_length=500)
    molecule_type: str | None = Field(default=None, max_length=120)
    structure: ChemblStructure | None = None
    aliases: list[AliasName] = Field(default_factory=list, max_length=200)


class ChemblMechanismReference(_SnapshotModel):
    ref_id: str = Field(default="", max_length=240)
    ref_type: str = Field(default="", max_length=120)
    ref_url: str = Field(default="", max_length=2000)


class ChemblMechanism(_PhasedSnapshotModel):
    mec_id: int = Field(gt=0)
    target_chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    molecule_chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    action_type: str | None = Field(default=None, max_length=120)
    mechanism_of_action: str = Field(min_length=1, max_length=500)
    direct_interaction: int | None = None
    molecular_mechanism: int | None = None
    mechanism_refs: list[ChemblMechanismReference] = Field(default_factory=list, max_length=20)


class ChemblCitation(_SnapshotModel):
    locator: str = Field(min_length=1, max_length=500)
    quote: str = Field(min_length=3, max_length=4000)


class ChemblSource(_SnapshotModel):
    api_root: str = Field(min_length=1, max_length=2000)
    mechanism_uri: str = Field(min_length=1, max_length=2000)
    molecule_uri: str = Field(min_length=1, max_length=2000)
    target_uri: str = Field(min_length=1, max_length=2000)
    license: Literal["CC BY-SA 3.0"]
    license_uri: str = Field(min_length=1, max_length=2000)


class ChemblSnapshot(_SnapshotModel):
    schema_version: Literal["pharma.chembl.mechanism.v1", "pharma.chembl.mechanism.v2", "pharma.chembl.mechanism.v3"]
    provider: Literal["ChEMBL"]
    target: ChemblTarget
    molecule: ChemblMolecule
    mechanism: ChemblMechanism
    citation: ChemblCitation
    source: ChemblSource
    activities: list[ChemblActivity] = Field(default_factory=list, max_length=10)
    activity_coverage: ChemblActivityCoverage = Field(default_factory=ChemblActivityCoverage)

    @model_validator(mode="after")
    def validate_enrichment_scope(self) -> ChemblSnapshot:
        if self.schema_version != SNAPSHOT_SCHEMA and (self.target.aliases or self.molecule.aliases):
            raise ValueError("Source-reported names require v3 snapshots")
        if self.target.aliases and self.target.target_type != "SINGLE PROTEIN":
            raise ValueError("Component synonyms cannot name a non-single-protein target")
        if self.schema_version.endswith("v1") and (self.activities or self.molecule.structure):
            raise ValueError("Legacy snapshots cannot include v2 enrichment")
        if len(self.activities) != self.activity_coverage.fetched - self.activity_coverage.excluded:
            raise ValueError("Activity coverage differs from snapshot observations")
        if len({item.activity_id for item in self.activities}) != len(self.activities):
            raise ValueError("Snapshot contains duplicate ChEMBL activity identifiers")
        return self


@dataclass(frozen=True)
class ChemblRecord:
    fact: ProgramFact
    target_profile: TargetProfileFact
    source_locator: str
    source_quote: str
    mechanism_id: int
    enrichment: tuple[StructureFact | ActivityFact, ...] = ()
    activity_coverage: ChemblActivityCoverage | None = None
    names: tuple[EntityAliasFact, ...] = ()


@dataclass(frozen=True)
class ChemblIdentityReconciliation:
    canonical_entity_id: str
    duplicate_entity_ids: tuple[str, ...]
    remapped_programs: int
    remapped_program_targets: int


def reconcile_chembl_target_links(
    session: Session,
    *,
    tenant_id: str,
    chembl_id: str,
    canonical_entity_id: str,
) -> ChemblIdentityReconciliation:
    """Point governed ChEMBL target relationships at one verified entity.

    ChEMBL snapshots can be replayed after a draft entity was created by an
    earlier governance policy. Updating only the entity identifier would leave
    program rows attached to hidden drafts, so this idempotent repair moves the
    two target relationship tables in the same transaction and preserves the
    draft entities and source history for auditability.
    """

    canonical = session.scalar(
        select(Entity).where(
            Entity.tenant_id == tenant_id,
            Entity.id == canonical_entity_id,
            Entity.entity_type == EntityType.TARGET,
            Entity.review_status == ReviewStatus.VERIFIED,
        )
    )
    if canonical is None:
        raise ValueError("ChEMBL reconciliation requires a verified target canonical entity")

    normalized_chembl_id = chembl_id.strip().upper()
    duplicates = [
        entity
        for entity in session.scalars(
            select(Entity).where(
                Entity.tenant_id == tenant_id,
                Entity.entity_type == EntityType.TARGET,
                Entity.id != canonical_entity_id,
                Entity.review_status == ReviewStatus.DRAFT,
            )
        )
        if str(entity.external_ids.get("chembl", "")).upper() == normalized_chembl_id
    ]
    duplicate_ids = tuple(sorted(entity.id for entity in duplicates))
    if not duplicate_ids:
        return ChemblIdentityReconciliation(canonical_entity_id, (), 0, 0)

    program_count = 0
    program_target_count = 0
    for program in session.scalars(
        select(DevelopmentProgram).where(
            DevelopmentProgram.tenant_id == tenant_id,
            DevelopmentProgram.target_entity_id.in_(duplicate_ids),
        )
    ):
        current_version = int(program.target_set_version or 1)
        current_targets = list(
            session.scalars(
                select(DevelopmentProgramTarget).where(
                    DevelopmentProgramTarget.tenant_id == tenant_id,
                    DevelopmentProgramTarget.program_id == program.id,
                    DevelopmentProgramTarget.target_set_version == current_version,
                )
            )
        )
        mapped_targets: list[tuple[str, DevelopmentProgramTarget | None]] = [
            (target.target_entity_id if target.target_entity_id not in duplicate_ids else canonical_entity_id, target)
            for target in current_targets
        ]
        if not mapped_targets:
            mapped_targets = [(canonical_entity_id, None)]
        if all(target is None or target_id == target.target_entity_id for target_id, target in mapped_targets):
            if program.target_entity_id != canonical_entity_id:
                program.target_entity_id = canonical_entity_id
                program.target_combination_key = canonical_entity_id
                program_count += 1
            continue
        next_version = current_version + 1
        for position, (target_id, previous) in enumerate(mapped_targets):
            session.add(
                DevelopmentProgramTarget(
                    tenant_id=tenant_id,
                    program_id=program.id,
                    target_set_version=next_version,
                    target_entity_id=target_id,
                    role=previous.role if previous is not None else ProgramTargetRole.PRIMARY,
                    position=previous.position if previous is not None else position,
                    source_document_id=previous.source_document_id
                    if previous is not None
                    else program.source_document_id,
                )
            )
            program_target_count += 1
        program.target_set_version = next_version
        program.target_entity_id = canonical_entity_id
        program.target_combination_key = "|".join(sorted(target_id for target_id, _ in mapped_targets))
        program_count += 1
    return ChemblIdentityReconciliation(
        canonical_entity_id=canonical_entity_id,
        duplicate_entity_ids=duplicate_ids,
        remapped_programs=program_count,
        remapped_program_targets=program_target_count,
    )


def adapter_policy_manifest() -> dict[str, object]:
    return {
        "adapter": ADAPTER_NAME,
        "automatic_source_updates": OFFICIAL_SOURCE_UPDATE_POLICY,
        "version": ADAPTER_VERSION,
        "snapshot_schema": SNAPSHOT_SCHEMA,
        "normalization_policy": STANDARDIZATION_VERSION,
        "enrichment_policy": (
            "Reported molecular structure and explicitly requested bounded activity observations; no replicate pooling."
        ),
        "fact_kind": "program",
        "identity_namespaces": ["chembl"],
        "phase_mapping": {str(value): phase.value for value, phase in CHEMBL_MAXIMUM_PHASES.items()},
        "phase_scope": "Reported maximum across indications; no regional approval or current status inference.",
        "status_policy": "ChEMBL mechanism records do not establish current active status; status remains unset.",
        "license": "CC BY-SA 3.0",
        "name_policy": "Reported molecule synonyms and single-protein component names; no inferred aliases or merges.",
    }


def is_authorized_chembl_asset(*, file_name: str, extension: str, authorization_scopes: list[str]) -> bool:
    return (
        extension.casefold() == ".json"
        and file_name.removesuffix(extension).isdigit()
        and "public:chembl" in authorization_scopes
    )


def parse_chembl_snapshot(content: bytes) -> ChemblRecord:
    if not content:
        raise ValueError("ChEMBL snapshot is empty")
    try:
        snapshot = ChemblSnapshot.model_validate_json(content)
    except (ValidationError, ValueError) as exc:
        raise ValueError("ChEMBL snapshot does not match the governed schema") from exc
    if snapshot.mechanism.target_chembl_id != snapshot.target.chembl_id:
        raise ValueError("ChEMBL snapshot target identity is inconsistent")
    if snapshot.mechanism.molecule_chembl_id != snapshot.molecule.chembl_id:
        raise ValueError("ChEMBL snapshot molecule identity is inconsistent")
    fact = ProgramFact(
        fact_kind="program",
        drug=EntityReference(
            entity_type=EntityType.DRUG,
            name=snapshot.molecule.pref_name,
            external_ids={"chembl": snapshot.molecule.chembl_id},
        ),
        targets=[
            ProgramTargetFact(
                role=ProgramTargetRole.PRIMARY,
                entity=EntityReference(
                    entity_type=EntityType.TARGET,
                    name=snapshot.target.pref_name,
                    external_ids={"chembl": snapshot.target.chembl_id},
                ),
            )
        ],
        phase=chembl_maximum_phase(snapshot.mechanism.max_phase),
        modality=public_program_modality(snapshot.mechanism.action_type, snapshot.molecule.molecule_type),
        drug_category=public_program_drug_category(
            snapshot.mechanism.action_type,
            snapshot.molecule.molecule_type,
        ),
        mechanism_of_action=snapshot.mechanism.mechanism_of_action,
        global_phase=None,
        program_tags=[],
        citation=Citation(
            locator=snapshot.citation.locator,
            quote=snapshot.citation.quote,
            confidence=1.0,
        ),
    )
    target_profile = TargetProfileFact(
        fact_kind="target_profile",
        subject=EntityReference(
            entity_type=EntityType.TARGET,
            name=snapshot.target.pref_name,
            external_ids={"chembl": snapshot.target.chembl_id},
        ),
        gene_symbol=snapshot.target.gene_symbol,
        uniprot_accession=snapshot.target.uniprot_accession,
        organism=snapshot.target.organism,
        target_class=snapshot.target.target_type,
        citation=Citation(
            locator=f"target:{snapshot.target.chembl_id}",
            quote=(
                f"target_chembl_id={snapshot.target.chembl_id}; "
                f"pref_name={snapshot.target.pref_name}; "
                f"gene_symbol={snapshot.target.gene_symbol or 'unknown'}; "
                f"uniprot_accession={snapshot.target.uniprot_accession or 'unknown'}"
            ),
            confidence=1.0,
        ),
    )
    return ChemblRecord(
        fact=fact,
        target_profile=target_profile,
        source_locator=snapshot.citation.locator,
        source_quote=snapshot.citation.quote,
        mechanism_id=snapshot.mechanism.mec_id,
        enrichment=tuple(
            enrichment_facts(
                compound=fact.drug,
                target=target_profile.subject,
                structure=snapshot.molecule.structure,
                activities=snapshot.activities,
            )
        ),
        activity_coverage=snapshot.activity_coverage,
        names=(
            *name_facts(target_profile.subject, snapshot.target.aliases, resource="target"),
            *name_facts(fact.drug, snapshot.molecule.aliases, resource="molecule"),
        ),
    )
