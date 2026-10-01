import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { workspaceUrl } from "../../lib/workspaceRouting";
import type { ResearchRouteContext } from "./routeContext";

const DiseaseView = lazy(() => import("../../views/DiseaseView").then((module) => ({ default: module.DiseaseView })));

export function DiseaseRoute({ context }: { context: ResearchRouteContext }) {
  const {
    location,
    selectedEntity,
    routeEntity,
    navigate,
    openDrugById,
    openEntityById,
    openTargetById,
    openDiseaseById,
    openOrganizationById,
    openEpidemiologyForDisease,
    openTrialById,
    openDealById,
    openPatentFamilyById,
    openRegulatoryEventById,
    openNewsEventById,
  } = context;
  return routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
    <Spinner label="正在恢复疾病档案深链接" />
  ) : location.invalidEntityId || routeEntity.error ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? "链接中的疾病 ID 无效"
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : "疾病档案链接加载失败"
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <DiseaseView
      disease={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
      activeSection={location.diseaseSection ?? "overview"}
      onSectionChange={(diseaseSection, replace = false) => navigate({ ...location, diseaseSection }, replace)}
      onOpenEpidemiology={openEpidemiologyForDisease}
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
      onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
      onOpenPatent={openPatentFamilyById}
      onOpenDeal={openDealById}
      onOpenRegulatoryEvent={openRegulatoryEventById}
      onOpenNewsEvent={openNewsEventById}
    />
  );
}
