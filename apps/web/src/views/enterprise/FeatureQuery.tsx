import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { useLocale } from "../../lib/i18n";
import { enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";

export function FeatureQuery<T>({
  query,
  children,
}: {
  query: UseQueryResult<T, Error>;
  children: (data: T) => ReactNode;
}) {
  useLocale();
  // Administrative data must disappear after a failed permission recheck.
  // Never replace a failed request with an empty, apparently successful list.
  if (query.isError) return <ErrorState message={query.error.message} retry={query.refetch} />;
  if (query.data === undefined) return <Spinner label={t("正在读取企业管理数据")} />;
  return children(query.data);
}
