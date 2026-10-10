import type { Ref } from "react";
import { ErrorState, Spinner, StatusBadge } from "../../components/common";
import { ApiError } from "../../lib/api";
import type { SearchProjectionStatusRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { FactoryDetailsPanel } from "./FactoryDetailsPanel";

export function projectionNeedsAttention(data: SearchProjectionStatusRead | undefined, error: Error | null): boolean {
  return Boolean(
    error ||
      data?.error ||
      data?.available === false ||
      (data?.deliveries.failed ?? 0) > 0 ||
      (data?.deliveries.dead ?? 0) > 0,
  );
}

export function SearchProjectionPanel({
  data: suppliedData,
  pending,
  error,
  onRetry,
  panelRef,
}: {
  data: SearchProjectionStatusRead | undefined;
  pending: boolean;
  error: Error | null;
  onRetry: () => void;
  panelRef?: Ref<HTMLDetailsElement>;
}) {
  useLocale();
  const denied = error instanceof ApiError && (error.status === 401 || error.status === 403);
  const data = denied ? undefined : suppliedData;
  const failed = data?.deliveries.failed ?? 0;
  const dead = data?.deliveries.dead ?? 0;
  const unavailable = Boolean(data && !data.available);
  const reveal = projectionNeedsAttention(data, error);
  const summary = error
    ? t("读取失败")
    : pending
      ? t("正在读取")
      : !data
        ? t("尚未观测")
        : unavailable
          ? t("服务不可用")
          : dead > 0
            ? t("{count} 条死信待处理", { count: dead })
            : failed > 0
              ? t("{count} 条失败投递", { count: failed })
              : t("服务可连接");
  return (
    <FactoryDetailsPanel
      title={t("检索投影运行状态")}
      panelRef={panelRef}
      reveal={reveal}
      summary={
        <StatusBadge
          value={error || unavailable ? "failed" : failed > 0 || dead > 0 ? "warning" : "unknown"}
          label={summary}
        />
      }
    >
      <p>{t("OpenSearch 集群、别名和投递队列来自服务状态；服务可连接不等于全部投递成功。")}</p>
      {error ? (
        <>
          <ErrorState message={t("检索投影状态读取失败")} retry={onRetry} />
          <p className="field-help">{error.message}</p>
        </>
      ) : null}
      {pending && !data ? <Spinner label={t("正在读取检索投影状态")} /> : null}
      {data ? (
        <>
          {error ? <p className="field-help">{t("上次读取的状态（非实时）")}</p> : null}
          {data.error ? (
            <p className="inline-error" role="alert">
              {data.error}
            </p>
          ) : null}
          <dl className="enterprise-tenant-details factory-projection-metrics">
            <div>
              <dt>{t("集群")}</dt>
              <dd>{data.cluster_name ?? t("未连接")}</dd>
            </div>
            <div>
              <dt>{t("集群状态")}</dt>
              <dd>{data.cluster_status ?? t(data.error ? "连接失败，请检查检索服务配置与网络" : "未披露")}</dd>
            </div>
            <div>
              <dt>{t("版本")}</dt>
              <dd>{data.version ?? t("未披露")}</dd>
            </div>
            <div>
              <dt>{t("索引别名")}</dt>
              <dd>{Object.keys(data.aliases).length}</dd>
            </div>
            <div>
              <dt>{t("待投递")}</dt>
              <dd>{data.deliveries.pending ?? 0}</dd>
            </div>
            <div>
              <dt>{t("失败投递")}</dt>
              <dd>{failed}</dd>
            </div>
            <div>
              <dt>{t("死信")}</dt>
              <dd>{dead}</dd>
            </div>
          </dl>
        </>
      ) : null}
    </FactoryDetailsPanel>
  );
}
