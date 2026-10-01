import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { workspaceUrl } from "../../lib/workspaceRouting";
import type { ResearchRouteContext } from "./routeContext";

const CompanyView = lazy(() => import("../../views/CompanyView").then((module) => ({ default: module.CompanyView })));

export function CompanyRoute({ context }: { context: ResearchRouteContext }) {
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
    <Spinner label="正在恢复公司档案深链接" />
  ) : location.invalidEntityId || routeEntity.error ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? "链接中的公司 ID 无效"
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : "公司档案链接加载失败"
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <CompanyView
      company={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
      activeSection={location.companySection ?? "overview"}
      onSectionChange={(companySection, replace = false) => navigate({ ...location, companySection }, replace)}
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
