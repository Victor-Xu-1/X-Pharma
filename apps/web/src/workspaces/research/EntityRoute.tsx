import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { useMessages } from "../../lib/i18n";
import { entityRouteMessages } from "../../lib/i18n/entityRoute";
import { workspaceUrl } from "../../lib/workspaceRouting";
import { researchRouteEntity, specializedResearchView } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

const EntityDossierView = lazy(() =>
  import("../../views/EntityDossierView").then((module) => ({ default: module.EntityDossierView })),
);

export function EntityRoute({ context }: { context: ResearchRouteContext }) {
  const text = useMessages(entityRouteMessages);
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
  const entity = researchRouteEntity(location.entityId, selectedEntity, routeEntity.data);
  const invalidMetadata = Boolean(routeEntity.data && routeEntity.data.id !== location.entityId);
  const specializing = Boolean(
    !location.invalidEntityId &&
      !routeEntity.error &&
      !invalidMetadata &&
      entity &&
      specializedResearchView(entity.entity_type),
  );
  return specializing || (routeEntity.isFetching && selectedEntity?.id !== location.entityId) ? (
    <Spinner label={text("正在恢复领域档案深链接")} />
  ) : location.invalidEntityId || routeEntity.error || invalidMetadata ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? text("链接中的实体 ID 无效")
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : invalidMetadata
              ? text("领域档案链接与请求实体不一致")
              : text("领域档案链接加载失败")
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <EntityDossierView
      entity={entity}
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
