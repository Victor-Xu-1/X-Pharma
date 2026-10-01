import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { workspaceUrl } from "../../lib/workspaceRouting";
import type { ResearchRouteContext } from "./routeContext";

const EntityDossierView = lazy(() =>
  import("../../views/EntityDossierView").then((module) => ({ default: module.EntityDossierView })),
);

export function EntityRoute({ context }: { context: ResearchRouteContext }) {
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
    openTrialById,
    openDealById,
    openPatentFamilyById,
    openRegulatoryEventById,
    openNewsEventById,
  } = context;
  return routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
    <Spinner label="正在恢复领域档案深链接" />
  ) : location.invalidEntityId || routeEntity.error ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? "链接中的实体 ID 无效"
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : "领域档案链接加载失败"
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <EntityDossierView
      entity={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
      activeSection={location.entitySection ?? "overview"}
      onSectionChange={(entitySection, replace = false) => navigate({ ...location, entitySection }, replace)}
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
