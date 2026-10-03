import { test } from "@playwright/test";
import { workbenchVisualTest } from "./fixtures/workbench-visual";
import { verifyBillingDispute } from "./workspace/billing-dispute";
import { verifyChemistry } from "./workspace/chemistry";
import { verifyClinicalNormalizedDrugOr } from "./workspace/clinical-normalized-drug-or";
import { verifyClinicalTrialSubscription } from "./workspace/clinical-trial-subscription";
import { verifyComparisonExport } from "./workspace/comparison-export";
import { verifyDenseServerSorting } from "./workspace/dense-server-sorting";
import { verifyDenseServerSortingSecondary } from "./workspace/dense-server-sorting-secondary";
import { verifyEnterpriseAdministration } from "./workspace/enterprise-administration";
import { verifyEntityResearchContinuity } from "./workspace/entity-research-continuity";
import { verifyEpidemiologyNewsSubscription } from "./workspace/epidemiology-news-subscription";
import { verifyEpidemiologyPatientPopulation } from "./workspace/epidemiology-patient-population";
import { verifyEvidenceResearchContinuity } from "./workspace/evidence-research-continuity";
import { verifyInternalLogin } from "./workspace/internal-login";
import { verifyKnowledgeGovernance } from "./workspace/knowledge-governance";
import { verifyKnowledgeResearchContinuity } from "./workspace/knowledge-research-continuity";
import { verifyMonitoring } from "./workspace/monitoring";
import { verifyPatentDealSubscription } from "./workspace/patent-deal-subscription";
import { verifyPermissionBoundary } from "./workspace/permission-boundary";
import { verifyPipelineDrugEntityFilter } from "./workspace/pipeline-drug-entity-filter";
import { verifyProfessionalErrorPermissionMatrix } from "./workspace/professional-error-permission-matrix";
import { verifyPublicLogin } from "./workspace/public-login";
import { verifyRealPermissionBoundary } from "./workspace/real-permission-boundary";
import { verifyRealTargetDossier } from "./workspace/real-target-dossier";
import { verifyRecentResearchContinuity } from "./workspace/recent-research-continuity";
import { verifyResearchPublicationTimeline } from "./workspace/research-publication-timeline";
import { verifySessionRecovery } from "./workspace/session-recovery";
import { verifyWorkspaceNavigation } from "./workspace/workspace-navigation";
import { verifyWorkspaceStates } from "./workspace/workspace-states";

test("[public-login][external-login] renders the external research login entry without overflow", verifyPublicLogin);
test("[internal-login] renders a distinct internal management entry", verifyInternalLogin);
workbenchVisualTest(
  "[workspace-navigation][workspace-isolation][research-workbench][internal-workbench][ingestion-replay][quarantine-governance][master-data-rollback][publication-governance][quality-operations][stable-deep-link][explorer-quick-detail-continuity][global-search-landscape][data-lifecycle][domain-export][result-pagination][result-to-comparison][cross-page-comparison][pipeline-intelligence][pipeline-cross-domain-signals][pipeline-cross-domain-navigation][pipeline-dense-results][pipeline-relationship-correctness][professional-patent-query][professional-deal-query][professional-regulatory-query][professional-epidemiology-query][professional-news-query][clinical-full-result-landscape][clinical-result-dense-fields][regulatory-intelligence][regulatory-result-correctness][regulatory-subscription][saved-search-maintenance][browser-quality][web-vitals-rum][initial-load-boundary][table-preference-server-continuity][query-cancellation][professional-query-state-matrix] authenticates and navigates both governed workbenches",
  verifyWorkspaceNavigation,
);
test(
  "[professional-error-permission-matrix] fails safely and recovers every professional query domain",
  verifyProfessionalErrorPermissionMatrix,
);
test(
  "[clinical-normalized-drug-or][clinical-role-groups][clinical-role-correctness][clinical-linked-program-correctness] combines normalized trial roles and linked drug attributes without cross-program matches",
  verifyClinicalNormalizedDrugOr,
);
test(
  "[pipeline-drug-entity-filter] keyboard-disambiguates one governed drug into a stable exact pipeline query",
  verifyPipelineDrugEntityFilter,
);
test(
  "[clinical-trial-subscription] saves, subscribes and replays the complete applied query",
  verifyClinicalTrialSubscription,
);
test(
  "[epidemiology-news-subscription][epidemiology-trend-correctness][news-result-correctness] saves, subscribes and replays disease burden and research event queries",
  verifyEpidemiologyNewsSubscription,
);
test(
  "[patent-deal-subscription] [patent-result-correctness] [deal-entity-query] [deal-asset-attributes] [deal-asset-multiselect] [deal-full-result-landscape] [deal-asset-correctness] saves, subscribes and replays both complete applied queries",
  verifyPatentDealSubscription,
);
test(
  "[entity-research-continuity] preserves dossier sections across keyboard, reload and history",
  verifyEntityResearchContinuity,
);
test(
  "[dense-server-sorting][disease-dossier] preserves governed ordering and disease research continuity",
  verifyDenseServerSorting,
);
test(
  "[dense-server-sorting-secondary] preserves governed deal, regulatory and epidemiology ordering",
  verifyDenseServerSortingSecondary,
);
test("[billing-dispute] opens and acknowledges a billing dispute in the human workspace", verifyBillingDispute);
test(
  "[enterprise-administration] manages tenant roles through the governed human workspace",
  verifyEnterpriseAdministration,
);
test("[monitoring] reviews saved searches and acknowledges a durable monitoring alert", verifyMonitoring);
test("[knowledge-governance] inspects governed coverage and traceable version changes", verifyKnowledgeGovernance);
test(
  "[knowledge-research-continuity] preserves a real governed topic across URL, reload and history",
  verifyKnowledgeResearchContinuity,
);
test(
  "[evidence-research-continuity] preserves a real licensed citation across URL, reload and history",
  verifyEvidenceResearchContinuity,
);
test(
  "[research-publication-timeline] switches to governed conference and publication chronology",
  verifyResearchPublicationTimeline,
);
test(
  "[epidemiology-patient-population] keeps a governed patient population filter stable",
  verifyEpidemiologyPatientPopulation,
);
test("[comparison-export] compares stable entities and downloads a governed export", verifyComparisonExport);
test("[session-recovery] presents and recovers from an identity service failure", verifySessionRecovery);
test("[permission-boundary] rejects a protected workspace deep link for a viewer", verifyPermissionBoundary);
test(
  "[real-permission-boundary] keeps external reads and rejects internal operations for a real viewer",
  verifyRealPermissionBoundary,
);
test(
  "[real-target-dossier] traverses a target dossier across governed domains through real APIs",
  verifyRealTargetDossier,
);
test(
  "[recent-research-continuity] restores only the current user's audited research after a browser reload",
  verifyRecentResearchContinuity,
);
test("[workspace-states] renders loading, error, recovery and empty search states", verifyWorkspaceStates);
test("[chemistry][chemistry-real-api] queries governed structures with the bundled RDKit runtime", verifyChemistry);
