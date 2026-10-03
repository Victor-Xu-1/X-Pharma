"""Canonical ORM namespace; each table is implemented in one domain module."""

from .accounts import (
    AccountInvitation as AccountInvitation,
)
from .accounts import (
    AccountRegistrationBudget as AccountRegistrationBudget,
)
from .accounts import (
    ApiKey as ApiKey,
)
from .accounts import OrganizationMembership as OrganizationMembership
from .accounts import (
    User as User,
)
from .accounts import (
    UserGroup as UserGroup,
)
from .accounts import (
    UserGroupMembership as UserGroupMembership,
)
from .accounts import (
    UserSession as UserSession,
)
from .audit import (
    AuditEvent as AuditEvent,
)
from .base import (
    Base as Base,
)
from .base import (
    TimestampMixin as TimestampMixin,
)
from .base import (
    new_uuid as new_uuid,
)
from .chemistry import (
    ActivityMeasurement as ActivityMeasurement,
)
from .chemistry import (
    Assay as Assay,
)
from .chemistry import (
    CompoundStructure as CompoundStructure,
)
from .collections import (
    ComparisonSet as ComparisonSet,
)
from .collections import (
    ComparisonSetMember as ComparisonSetMember,
)
from .collections import (
    ComparisonSetVersion as ComparisonSetVersion,
)
from .commercial_billing import (
    BillingAdjustment as BillingAdjustment,
)
from .commercial_billing import (
    BillingDispute as BillingDispute,
)
from .commercial_billing import (
    BillingDisputeEvent as BillingDisputeEvent,
)
from .commercial_billing import (
    BillingPeriodStatement as BillingPeriodStatement,
)
from .commercial_billing import (
    CommercialReconciliationRun as CommercialReconciliationRun,
)
from .commercial_billing import (
    InvoiceReference as InvoiceReference,
)
from .commercial_clients import (
    AgentClient as AgentClient,
)
from .commercial_clients import (
    AgentClientSubject as AgentClientSubject,
)
from .commercial_clients import (
    BillingAccount as BillingAccount,
)
from .commercial_clients import (
    CommercialExportPolicy as CommercialExportPolicy,
)
from .commercial_clients import (
    CommercialRiskPolicy as CommercialRiskPolicy,
)
from .commercial_lifecycle import (
    DataExportJob as DataExportJob,
)
from .commercial_lifecycle import (
    DataLifecycleEvent as DataLifecycleEvent,
)
from .commercial_lifecycle import (
    DataRetentionPolicy as DataRetentionPolicy,
)
from .commercial_lifecycle import (
    LegalHold as LegalHold,
)
from .commercial_subscription import (
    CommercialEntitlement as CommercialEntitlement,
)
from .commercial_subscription import (
    CommercialSubscription as CommercialSubscription,
)
from .commercial_subscription import (
    CreditGrant as CreditGrant,
)
from .commercial_subscription import (
    RateCardItem as RateCardItem,
)
from .commercial_subscription import (
    RateCardVersion as RateCardVersion,
)
from .commercial_usage import (
    CommercialCoverageRecord as CommercialCoverageRecord,
)
from .commercial_usage import (
    CommercialLedgerEntry as CommercialLedgerEntry,
)
from .commercial_usage import (
    CommercialPolicyEvent as CommercialPolicyEvent,
)
from .commercial_usage import (
    CommercialRiskCase as CommercialRiskCase,
)
from .commercial_usage import (
    UsageEvent as UsageEvent,
)
from .commercial_usage import (
    UsageReservation as UsageReservation,
)
from .commercial_usage import (
    UsageSettlement as UsageSettlement,
)
from .deals import (
    DealAssetAssociation as DealAssetAssociation,
)
from .deals import (
    DealPartyAssociation as DealPartyAssociation,
)
from .deals import (
    DealProfile as DealProfile,
)
from .deals import (
    DealRight as DealRight,
)
from .enums import (
    AssetStatus as AssetStatus,
)
from .enums import (
    BillingAccountStatus as BillingAccountStatus,
)
from .enums import (
    CommercialLedgerEventType as CommercialLedgerEventType,
)
from .enums import (
    DataSourceState as DataSourceState,
)
from .enums import (
    DataSourceType as DataSourceType,
)
from .enums import (
    DealDirection as DealDirection,
)
from .enums import (
    DealPartyRole as DealPartyRole,
)
from .enums import (
    DealRightType as DealRightType,
)
from .enums import (
    DealStatus as DealStatus,
)
from .enums import (
    DevelopmentPhase as DevelopmentPhase,
)
from .enums import (
    EntityType as EntityType,
)
from .enums import (
    GovernanceStatus as GovernanceStatus,
)
from .enums import (
    KnowledgePageStatus as KnowledgePageStatus,
)
from .enums import (
    MeasurementRelation as MeasurementRelation,
)
from .enums import (
    OutboxState as OutboxState,
)
from .enums import (
    ProgramOrganizationRole as ProgramOrganizationRole,
)
from .enums import (
    ProgramTargetRole as ProgramTargetRole,
)
from .enums import (
    ProjectionDeliveryState as ProjectionDeliveryState,
)
from .enums import (
    QuarantineStatus as QuarantineStatus,
)
from .enums import (
    RegulatoryDesignationType as RegulatoryDesignationType,
)
from .enums import (
    RegulatoryLabelChangeType as RegulatoryLabelChangeType,
)
from .enums import (
    RegulatorySafetySeverity as RegulatorySafetySeverity,
)
from .enums import (
    RegulatorySafetySignalType as RegulatorySafetySignalType,
)
from .enums import (
    RegulatorySafetyStatus as RegulatorySafetyStatus,
)
from .enums import (
    ResolutionStatus as ResolutionStatus,
)
from .enums import (
    ReviewStatus as ReviewStatus,
)
from .enums import (
    RunState as RunState,
)
from .enums import (
    SavedSearchVisibility as SavedSearchVisibility,
)
from .enums import (
    SourceAssetState as SourceAssetState,
)
from .enums import (
    SourceVersionState as SourceVersionState,
)
from .enums import (
    StageStatus as StageStatus,
)
from .enums import (
    SubscriptionStatus as SubscriptionStatus,
)
from .enums import (
    TrialEntityRole as TrialEntityRole,
)
from .enums import (
    TrialResultDisclosureType as TrialResultDisclosureType,
)
from .enums import (
    TrialResultEvaluation as TrialResultEvaluation,
)
from .enums import (
    UsageReservationState as UsageReservationState,
)
from .enums import (
    UserRole as UserRole,
)
from .epidemiology import (
    EpidemiologyObservation as EpidemiologyObservation,
)
from .epidemiology import (
    PatientPopulation as PatientPopulation,
)
from .epidemiology import (
    PatientPopulationEntityLink as PatientPopulationEntityLink,
)
from .evidence import (
    EvidenceClaim as EvidenceClaim,
)
from .evidence import (
    Relationship as Relationship,
)
from .evidence import (
    SourceDocument as SourceDocument,
)
from .governance import (
    ExtractionRun as ExtractionRun,
)
from .governance import (
    FactProvenanceLink as FactProvenanceLink,
)
from .governance import (
    FactWithdrawalTombstone as FactWithdrawalTombstone,
)
from .governance import (
    GovernancePublicationBatch as GovernancePublicationBatch,
)
from .governance import (
    GovernancePublicationBatchItem as GovernancePublicationBatchItem,
)
from .governance import (
    ReviewTask as ReviewTask,
)
from .governance import (
    StagedFact as StagedFact,
)
from .identity import (
    Entity as Entity,
)
from .identity import (
    EntityAlias as EntityAlias,
)
from .identity import (
    EntityCanonicalLink as EntityCanonicalLink,
)
from .identity import (
    EntityIdentifier as EntityIdentifier,
)
from .identity import (
    EntityOntologyMapping as EntityOntologyMapping,
)
from .identity import (
    EntityResolutionCase as EntityResolutionCase,
)
from .identity import (
    EntityResolutionDecision as EntityResolutionDecision,
)
from .identity import (
    OntologyTerm as OntologyTerm,
)
from .ingestion import (
    DataSource as DataSource,
)
from .ingestion import (
    IngestionAsset as IngestionAsset,
)
from .ingestion import (
    IngestionFinding as IngestionFinding,
)
from .ingestion import (
    IngestionRun as IngestionRun,
)
from .ingestion import (
    IngestionRunOperation as IngestionRunOperation,
)
from .ingestion import (
    RetrievalProjection as RetrievalProjection,
)
from .ingestion import (
    SourceAsset as SourceAsset,
)
from .ingestion import (
    SourceVersion as SourceVersion,
)
from .ingestion import (
    SourceVersionOperation as SourceVersionOperation,
)
from .ingestion import (
    SourceVersionQuarantineDecision as SourceVersionQuarantineDecision,
)
from .knowledge import (
    KnowledgeCitation as KnowledgeCitation,
)
from .knowledge import (
    KnowledgeLink as KnowledgeLink,
)
from .knowledge import (
    KnowledgePage as KnowledgePage,
)
from .knowledge import (
    KnowledgePageVersion as KnowledgePageVersion,
)
from .monitoring import (
    MonitoringAlert as MonitoringAlert,
)
from .monitoring import (
    MonitoringAlertReceipt as MonitoringAlertReceipt,
)
from .monitoring import (
    MonitoringTopic as MonitoringTopic,
)
from .monitoring import (
    SavedSearch as SavedSearch,
)
from .monitoring import (
    SavedSearchVersion as SavedSearchVersion,
)
from .news import (
    NewsEvent as NewsEvent,
)
from .patents import (
    PatentFamily as PatentFamily,
)
from .programs import (
    DevelopmentProgram as DevelopmentProgram,
)
from .programs import (
    DevelopmentProgramOrganization as DevelopmentProgramOrganization,
)
from .programs import (
    DevelopmentProgramTarget as DevelopmentProgramTarget,
)
from .projections import (
    OutboxEvent as OutboxEvent,
)
from .projections import (
    ProjectionDelivery as ProjectionDelivery,
)
from .projections import (
    ProjectionMaintenanceJob as ProjectionMaintenanceJob,
)
from .quality import (
    DataQualityIssue as DataQualityIssue,
)
from .quality import (
    DataQualityIssueEvent as DataQualityIssueEvent,
)
from .quality import (
    DataQualitySnapshot as DataQualitySnapshot,
)
from .regulatory import (
    RegulatoryEvent as RegulatoryEvent,
)
from .targets import (
    TargetEvidenceObservation as TargetEvidenceObservation,
)
from .targets import (
    TargetProfile as TargetProfile,
)
from .tenancy import (
    LLMProviderConfig as LLMProviderConfig,
)
from .tenancy import (
    Tenant as Tenant,
)
from .tenancy import (
    TenantDataset as TenantDataset,
)
from .trials import (
    ClinicalTrialEntityRole as ClinicalTrialEntityRole,
)
from .trials import (
    ClinicalTrialProfile as ClinicalTrialProfile,
)
from .trials import (
    ClinicalTrialResultDisclosure as ClinicalTrialResultDisclosure,
)
from .workspace import (
    WorkspaceExportEvent as WorkspaceExportEvent,
)
from .workspace import (
    WorkspaceExportPolicy as WorkspaceExportPolicy,
)
from .workspace import (
    WorkspaceTablePreference as WorkspaceTablePreference,
)
