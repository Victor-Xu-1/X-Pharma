import { Suspense } from "react";
import { Spinner } from "../../components/common";
import { ResearchContinuity } from "../../components/ResearchContinuity";
import { WorkspaceShell } from "../../components/WorkspaceShell";
import { ChemistryRoute } from "./ChemistryRoute";
import { CollectionsRoute } from "./CollectionsRoute";
import { CompanyRoute } from "./CompanyRoute";
import { DealsRoute } from "./DealsRoute";
import { DiseaseRoute } from "./DiseaseRoute";
import { DrugRoute } from "./DrugRoute";
import { EntityRoute } from "./EntityRoute";
import { EpidemiologyRoute } from "./EpidemiologyRoute";
import { EvidenceRoute } from "./EvidenceRoute";
import { ExplorerRoute } from "./ExplorerRoute";
import { KnowledgeRoute } from "./KnowledgeRoute";
import { MonitoringRoute } from "./MonitoringRoute";
import { NewsRoute } from "./NewsRoute";
import { OverviewRoute } from "./OverviewRoute";
import { PatentsRoute } from "./PatentsRoute";
import { PipelineRoute } from "./PipelineRoute";
import { RegulatoryRoute } from "./RegulatoryRoute";
import { ResearchReturnControl } from "./ResearchReturnControl";
import type { WorkspaceSessionProps } from "./routeContext";
import { TargetRoute } from "./TargetRoute";
import { TrialsRoute } from "./TrialsRoute";
import { useResearchNavigation } from "./useResearchNavigation";

export function ResearchWorkspace(props: WorkspaceSessionProps) {
  const navigation = useResearchNavigation();
  const { location, pendingNavigationView, navigateToView, openEntityById } = navigation;
  const { user, onLogout, logoutPending, logoutError } = props;
  const context = { ...navigation, ...props };
  return (
    <WorkspaceShell
      user={user}
      activeWorkbench="research"
      activeView={location.view}
      pendingView={pendingNavigationView}
      sourceView={navigation.activeReturnLocation?.view}
      researchDetail={Boolean(
        location.trialId || location.patentId || location.dealId || location.regulatoryEventId || location.newsEventId,
      )}
      onLogout={onLogout}
      logoutPending={logoutPending}
      logoutError={logoutError}
      onView={navigateToView}
    >
      <ResearchReturnControl context={context} />
      <Suspense fallback={<Spinner label="正在加载研究工作区" />}>
        {location.view === "explorer" ? <ResearchContinuity onOpenEntity={openEntityById} /> : null}
        {location.view === "overview" ? <OverviewRoute context={context} /> : null}
        {location.view === "explorer" ? <ExplorerRoute context={context} /> : null}
        {location.view === "chemistry" ? <ChemistryRoute context={context} /> : null}
        {location.view === "pipeline" ? <PipelineRoute context={context} /> : null}
        {location.view === "trials" ? <TrialsRoute context={context} /> : null}
        {location.view === "patents" ? <PatentsRoute context={context} /> : null}
        {location.view === "deals" ? <DealsRoute context={context} /> : null}
        {location.view === "regulatory" ? <RegulatoryRoute context={context} /> : null}
        {location.view === "epidemiology" ? <EpidemiologyRoute context={context} /> : null}
        {location.view === "news" ? <NewsRoute context={context} /> : null}
        {location.view === "target" ? <TargetRoute context={context} /> : null}
        {location.view === "drug" ? <DrugRoute context={context} /> : null}
        {location.view === "company" ? <CompanyRoute context={context} /> : null}
        {location.view === "disease" ? <DiseaseRoute context={context} /> : null}
        {location.view === "entity" ? <EntityRoute context={context} /> : null}
        {location.view === "evidence" ? <EvidenceRoute context={context} /> : null}
        {location.view === "knowledge" ? <KnowledgeRoute context={context} /> : null}
        {location.view === "monitoring" ? <MonitoringRoute context={context} /> : null}
        {location.view === "collections" ? <CollectionsRoute context={context} /> : null}
      </Suspense>
    </WorkspaceShell>
  );
}
