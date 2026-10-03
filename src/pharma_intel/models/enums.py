from __future__ import annotations

import enum


class _PersistedStringEnum(enum.StrEnum):
    """Keep established symbolic formatting while modernizing the string enum type."""

    __str__ = enum.Enum.__str__
    __format__ = enum.Enum.__format__


class EntityType(_PersistedStringEnum):
    DRUG = "drug"
    TARGET = "target"
    DISEASE = "disease"
    ORGANIZATION = "organization"
    CLINICAL_TRIAL = "clinical_trial"
    PATENT = "patent"
    TRANSACTION = "transaction"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    PERSON = "person"


class ReviewStatus(_PersistedStringEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ResolutionStatus(_PersistedStringEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVERTED = "reverted"


class UserRole(_PersistedStringEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AssetStatus(_PersistedStringEnum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"
    SOURCE_UNAVAILABLE = "source_unavailable"
    EXCLUDED = "excluded"


class DevelopmentPhase(_PersistedStringEnum):
    DISCOVERY = "discovery"
    PRECLINICAL = "preclinical"
    IND = "ind"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    FILED = "filed"
    APPROVED = "approved"
    DISCONTINUED = "discontinued"


class ProgramOrganizationRole(_PersistedStringEnum):
    ORIGINATOR = "originator"
    COLLABORATOR = "collaborator"
    LICENSEE = "licensee"
    LICENSOR = "licensor"
    MANUFACTURER = "manufacturer"
    OTHER = "other"


class ProgramTargetRole(_PersistedStringEnum):
    PRIMARY = "primary"
    COMBINATION = "combination"


class TrialResultEvaluation(_PersistedStringEnum):
    UNFAVORABLE = "unfavorable"
    NOT_SUPERIOR = "not_superior"
    NON_INFERIOR = "non_inferior"
    SIMILAR = "similar"
    POSITIVE = "positive"
    SUPERIOR = "superior"
    TERMINATED = "terminated"


class TrialEntityRole(_PersistedStringEnum):
    INVESTIGATIONAL_DRUG = "investigational_drug"
    COMBINATION_DRUG = "combination_drug"
    INVESTIGATIONAL_TARGET = "investigational_target"
    COMBINATION_TARGET = "combination_target"


class TrialResultDisclosureType(_PersistedStringEnum):
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_ABSTRACT = "conference_abstract"
    CONFERENCE_PRESENTATION = "conference_presentation"
    REGISTRY_RESULT = "registry_result"
    PRESS_RELEASE = "press_release"
    POSTER = "poster"
    OTHER = "other"


class DealStatus(_PersistedStringEnum):
    ANNOUNCED = "announced"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class DealDirection(_PersistedStringEnum):
    DOMESTIC = "domestic"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    CROSS_BORDER = "cross_border"
    GLOBAL = "global"
    UNDISCLOSED = "undisclosed"


class DealPartyRole(_PersistedStringEnum):
    LICENSOR = "licensor"
    LICENSEE = "licensee"
    SELLER = "seller"
    BUYER = "buyer"
    ACQUIRER = "acquirer"
    TARGET = "target"
    PARTNER = "partner"
    INVESTOR = "investor"
    INVESTEE = "investee"
    OTHER = "other"


class DealRightType(_PersistedStringEnum):
    RESEARCH = "research"
    DEVELOPMENT = "development"
    MANUFACTURING = "manufacturing"
    COMMERCIALIZATION = "commercialization"
    CO_DEVELOPMENT = "co_development"
    CO_PROMOTION = "co_promotion"
    DISTRIBUTION = "distribution"
    OPTION = "option"
    OTHER = "other"


class RegulatoryDesignationType(_PersistedStringEnum):
    BREAKTHROUGH_THERAPY = "breakthrough_therapy"
    FAST_TRACK = "fast_track"
    PRIORITY_REVIEW = "priority_review"
    ACCELERATED_APPROVAL = "accelerated_approval"
    ORPHAN_DRUG = "orphan_drug"
    PRIME = "prime"
    SAKIGAKE = "sakigake"
    CONDITIONAL_MARKETING_AUTHORISATION = "conditional_marketing_authorisation"
    OTHER = "other"


class RegulatoryLabelChangeType(_PersistedStringEnum):
    INITIAL_LABEL = "initial_label"
    INDICATION_EXPANSION = "indication_expansion"
    POPULATION_EXPANSION = "population_expansion"
    RESTRICTION = "restriction"
    DOSING_UPDATE = "dosing_update"
    ADMINISTRATION_UPDATE = "administration_update"
    SAFETY_UPDATE = "safety_update"
    BOXED_WARNING = "boxed_warning"
    CONTRAINDICATION = "contraindication"
    OTHER = "other"


class RegulatorySafetySignalType(_PersistedStringEnum):
    ADVERSE_EVENT = "adverse_event"
    BOXED_WARNING = "boxed_warning"
    CONTRAINDICATION = "contraindication"
    RISK_MANAGEMENT = "risk_management"
    RECALL = "recall"
    CLINICAL_HOLD = "clinical_hold"
    POSTMARKETING_REQUIREMENT = "postmarketing_requirement"
    OTHER = "other"


class RegulatorySafetySeverity(_PersistedStringEnum):
    INFORMATIONAL = "informational"
    MODERATE = "moderate"
    SERIOUS = "serious"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class RegulatorySafetyStatus(_PersistedStringEnum):
    DETECTED = "detected"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class MeasurementRelation(_PersistedStringEnum):
    EQUAL = "="
    LESS_THAN = "<"
    LESS_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_OR_EQUAL = ">="
    APPROXIMATE = "~"


class DataSourceType(_PersistedStringEnum):
    FOLDER = "folder"
    HTTP_MANIFEST = "http_manifest"
    CLINICALTRIALS_GOV = "clinicaltrials_gov"
    PUBMED = "pubmed"
    CHEMBL = "chembl"
    S3_SNAPSHOT = "s3_snapshot"
    SFTP_SNAPSHOT = "sftp_snapshot"
    SMB_SNAPSHOT = "smb_snapshot"


class DataSourceState(_PersistedStringEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class SourceAssetState(_PersistedStringEnum):
    ACTIVE = "active"
    MISSING = "missing"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DELETED = "deleted"


class SourceVersionState(_PersistedStringEnum):
    DISCOVERED = "discovered"
    SNAPSHOTTED = "snapshotted"
    PARSED = "parsed"
    INDEXED = "indexed"
    GOVERNANCE_PENDING = "governance_pending"
    REVIEW_PENDING = "review_pending"
    PUBLISHED = "published"
    ASSET_ONLY = "asset_only"
    FAILED = "failed"


class QuarantineStatus(_PersistedStringEnum):
    NOT_APPLICABLE = "not_applicable"
    PENDING_REVIEW = "pending_review"
    HELD = "held"
    RESCAN_REQUESTED = "rescan_requested"
    REJECTED = "rejected"
    CLEARED = "cleared"


class RunState(_PersistedStringEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    PARTIAL = "partial"


class StageStatus(_PersistedStringEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class GovernanceStatus(_PersistedStringEnum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    CONFLICT = "conflict"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


class KnowledgePageStatus(_PersistedStringEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OutboxState(_PersistedStringEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class ProjectionDeliveryState(_PersistedStringEnum):
    PROCESSING = "processing"
    RETRY = "retry"
    SUCCEEDED = "succeeded"
    DEAD = "dead"


class SavedSearchVisibility(_PersistedStringEnum):
    PRIVATE = "private"
    TENANT = "tenant"


class BillingAccountStatus(_PersistedStringEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class SubscriptionStatus(_PersistedStringEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"
    EXPIRED = "expired"


class UsageReservationState(_PersistedStringEnum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    EXPIRED = "expired"


class CommercialLedgerEventType(_PersistedStringEnum):
    CREDIT_GRANTED = "credit_granted"
    USAGE_RESERVED = "usage_reserved"
    USAGE_SETTLED = "usage_settled"
    RESERVATION_RELEASED = "reservation_released"
    RESERVATION_EXPIRED = "reservation_expired"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"
