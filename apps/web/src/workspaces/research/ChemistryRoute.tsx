import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import type { ChemistrySavedSearchQuery } from "../../lib/generated";
import type { ResearchRouteContext } from "./routeContext";

const ChemistryView = lazy(() =>
  import("../../views/ChemistryView").then((module) => ({ default: module.ChemistryView })),
);

export function ChemistryRoute({ context }: { context: ResearchRouteContext }) {
  const { location, routeChemistrySavedSearch, navigate, openEntityById } = context;
  return location.invalidChemistrySavedSearchId ? (
    <ErrorState message="结构检索保存链接无效" />
  ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.isPending ? (
    <Spinner label="正在恢复已保存结构检索" />
  ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.error ? (
    <ErrorState
      message={
        routeChemistrySavedSearch.error instanceof Error
          ? routeChemistrySavedSearch.error.message
          : "已保存结构检索暂不可用"
      }
      retry={() => void routeChemistrySavedSearch.refetch()}
    />
  ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.data?.query_type !== "chemistry_search" ? (
    <ErrorState message="保存检索类型与结构检索页面不匹配" />
  ) : (
    <ChemistryView
      onInspectEntity={openEntityById}
      initialSearch={
        routeChemistrySavedSearch.data?.query_type === "chemistry_search"
          ? (routeChemistrySavedSearch.data.query_json as ChemistrySavedSearchQuery)
          : null
      }
      savedSearchId={location.chemistrySavedSearchId}
      onSearchCommit={() =>
        location.chemistrySavedSearchId
          ? navigate({ ...location, chemistrySavedSearchId: null, invalidChemistrySavedSearchId: false }, true)
          : undefined
      }
      onSavedSearch={(saved) =>
        navigate({ ...location, chemistrySavedSearchId: saved.id, invalidChemistrySavedSearchId: false }, true)
      }
    />
  );
}
