import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { workspaceUrl } from "../../lib/workspaceRouting";
import { researchReturnLabel } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

const DrugView = lazy(() => import("../../views/DrugView").then((module) => ({ default: module.DrugView })));

export function DrugRoute({ context }: { context: ResearchRouteContext }) {
  const {
    location,
    selectedEntity,
    activeReturnLocation,
    routeEntity,
    navigate,
    openDrugById,
    openEntityById,
    openTargetById,
    openDiseaseById,
    openOrganizationById,
    openTrialById,
    openDealById,
    openPatentFamilyById,
    openRegulatoryEventById,
    openNewsEventById,
  } = context;
  return routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
    <Spinner label="正在恢复药物档案深链接" />
  ) : location.invalidEntityId || routeEntity.error ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? "链接中的药物 ID 无效"
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : "药物档案链接加载失败"
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <DrugView
      drug={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
      activeSection={location.drugSection ?? "overview"}
      programOffset={location.offset ?? 0}
      onProgramOffsetChange={(offset) => navigate({ ...location, offset })}
      onSectionChange={(drugSection, replace = false) => navigate({ ...location, drugSection, offset: 0 }, replace)}
      onOpenEntity={openEntityById}
      onOpenDrug={(entityId) => openDrugById(entityId, location.returnTo)}
      onOpenTarget={(entityId) => openTargetById(entityId, workspaceUrl(location))}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
      onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
      onOpenPatent={openPatentFamilyById}
      onOpenDeal={openDealById}
      onOpenRegulatoryEvent={openRegulatoryEventById}
      onOpenNewsEvent={openNewsEventById}
      returnTargetId={
        activeReturnLocation?.view === "target" && activeReturnLocation.targetSection === "pipeline"
          ? (activeReturnLocation.entityId ?? undefined)
          : undefined
      }
      onReturnToTarget={
        activeReturnLocation?.view === "target" && activeReturnLocation.targetSection === "pipeline"
          ? () => navigate(activeReturnLocation, true, true)
          : undefined
      }
      returnLabel={
        activeReturnLocation?.view === "target" && activeReturnLocation.targetSection === "pipeline"
          ? undefined
          : researchReturnLabel(activeReturnLocation)
      }
      onReturn={activeReturnLocation ? () => navigate(activeReturnLocation, true, true) : undefined}
    />
  );
}
