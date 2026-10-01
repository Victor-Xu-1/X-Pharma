from __future__ import annotations

import enum


class EntityType(str, enum.Enum):
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


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ResolutionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVERTED = "reverted"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AssetStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"
    SOURCE_UNAVAILABLE = "source_unavailable"
    EXCLUDED = "excluded"


class DevelopmentPhase(str, enum.Enum):
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


class ProgramOrganizationRole(str, enum.Enum):
    ORIGINATOR = "originator"
    COLLABORATOR = "collaborator"
    LICENSEE = "licensee"
    LICENSOR = "licensor"
    MANUFACTURER = "manufacturer"
    OTHER = "other"


class ProgramTargetRole(str, enum.Enum):
    PRIMARY = "primary"
    COMBINATION = "combination"


class TrialResultEvaluation(str, enum.Enum):
    UNFAVORABLE = "unfavorable"
    NOT_SUPERIOR = "not_superior"
    NON_INFERIOR = "non_inferior"
    SIMILAR = "similar"
    POSITIVE = "positive"
    SUPERIOR = "superior"
    TERMINATED = "terminated"


class TrialEntityRole(str, enum.Enum):
    INVESTIGATIONAL_DRUG = "investigational_drug"
    COMBINATION_DRUG = "combination_drug"
    INVESTIGATIONAL_TARGET = "investigational_target"
    COMBINATION_TARGET = "combination_target"


class TrialResultDisclosureType(str, enum.Enum):
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_ABSTRACT = "conference_abstract"
    CONFERENCE_PRESENTATION = "conference_presentation"
    REGISTRY_RESULT = "registry_result"
    PRESS_RELEASE = "press_release"
    POSTER = "poster"
    OTHER = "other"


class DealStatus(str, enum.Enum):
    ANNOUNCED = "announced"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class DealDirection(str, enum.Enum):
    DOMESTIC = "domestic"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    CROSS_BORDER = "cross_border"
    GLOBAL = "global"
    UNDISCLOSED = "undisclosed"


class DealPartyRole(str, enum.Enum):
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


class DealRightType(str, enum.Enum):
    RESEARCH = "research"
    DEVELOPMENT = "development"
    MANUFACTURING = "manufacturing"
    COMMERCIALIZATION = "commercialization"
    CO_DEVELOPMENT = "co_development"
    CO_PROMOTION = "co_promotion"
    DISTRIBUTION = "distribution"
    OPTION = "option"
    OTHER = "other"


class RegulatoryDesignationType(str, enum.Enum):
    BREAKTHROUGH_THERAPY = "breakthrough_therapy"
    FAST_TRACK = "fast_track"
    PRIORITY_REVIEW = "priority_review"
    ACCELERATED_APPROVAL = "accelerated_approval"
    ORPHAN_DRUG = "orphan_drug"
    PRIME = "prime"
    SAKIGAKE = "sakigake"
    CONDITIONAL_MARKETING_AUTHORISATION = "conditional_marketing_authorisation"
    OTHER = "other"


class RegulatoryLabelChangeType(str, enum.Enum):
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


class RegulatorySafetySignalType(str, enum.Enum):
    ADVERSE_EVENT = "adverse_event"
    BOXED_WARNING = "boxed_warning"
    CONTRAINDICATION = "contraindication"
    RISK_MANAGEMENT = "risk_management"
    RECALL = "recall"
    CLINICAL_HOLD = "clinical_hold"
    POSTMARKETING_REQUIREMENT = "postmarketing_requirement"
    OTHER = "other"


class RegulatorySafetySeverity(str, enum.Enum):
    INFORMATIONAL = "informational"
    MODERATE = "moderate"
    SERIOUS = "serious"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class RegulatorySafetyStatus(str, enum.Enum):
    DETECTED = "detected"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class MeasurementRelation(str, enum.Enum):
    EQUAL = "="
    LESS_THAN = "<"
    LESS_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_OR_EQUAL = ">="
    APPROXIMATE = "~"


class DataSourceType(str, enum.Enum):
    FOLDER = "folder"
    HTTP_MANIFEST = "http_manifest"
    CLINICALTRIALS_GOV = "clinicaltrials_gov"
    PUBMED = "pubmed"
    CHEMBL = "chembl"
    S3_SNAPSHOT = "s3_snapshot"
    SFTP_SNAPSHOT = "sftp_snapshot"
    SMB_SNAPSHOT = "smb_snapshot"


class DataSourceState(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class SourceAssetState(str, enum.Enum):
    ACTIVE = "active"
    MISSING = "missing"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DELETED = "deleted"


class SourceVersionState(str, enum.Enum):
    DISCOVERED = "discovered"
    SNAPSHOTTED = "snapshotted"
    PARSED = "parsed"
    INDEXED = "indexed"
    GOVERNANCE_PENDING = "governance_pending"
    REVIEW_PENDING = "review_pending"
    PUBLISHED = "published"
    ASSET_ONLY = "asset_only"
    FAILED = "failed"


class QuarantineStatus(str, enum.Enum):
    NOT_APPLICABLE = "not_applicable"
    PENDING_REVIEW = "pending_review"
    HELD = "held"
    RESCAN_REQUESTED = "rescan_requested"
    REJECTED = "rejected"
    CLEARED = "cleared"


class RunState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    PARTIAL = "partial"


class StageStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class GovernanceStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    CONFLICT = "conflict"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


class KnowledgePageStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OutboxState(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class ProjectionDeliveryState(str, enum.Enum):
    PROCESSING = "processing"
    RETRY = "retry"
    SUCCEEDED = "succeeded"
    DEAD = "dead"


class SavedSearchVisibility(str, enum.Enum):
    PRIVATE = "private"
    TENANT = "tenant"


class BillingAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"
    EXPIRED = "expired"


class UsageReservationState(str, enum.Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    EXPIRED = "expired"


class CommercialLedgerEventType(str, enum.Enum):
    CREDIT_GRANTED = "credit_granted"
    USAGE_RESERVED = "usage_reserved"
    USAGE_SETTLED = "usage_settled"
    RESERVATION_RELEASED = "reservation_released"
    RESERVATION_EXPIRED = "reservation_expired"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"
