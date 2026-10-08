import { ErrorState, Spinner, StatusBadge } from "../../components/common";
import type { SearchProjectionStatusRead } from "../../lib/generated";
import { FactoryDetailsPanel } from "./FactoryDetailsPanel";

export function SearchProjectionPanel({
  data,
  pending,
  error,
  onRetry,
}: {
  data: SearchProjectionStatusRead | undefined;
  pending: boolean;
  error: Error | null;
  onRetry: () => void;
}) {
  const failed = data?.deliveries.failed ?? 0;
  const dead = data?.deliveries.dead ?? 0;
  const unavailable = Boolean(data && !data.available);
  const reveal = Boolean(error || unavailable || failed > 0 || dead > 0);
  const summary = error
    ? "读取失败"
    : pending
      ? "正在读取"
      : unavailable
        ? "服务不可用"
        : dead > 0
          ? `${dead} 条死信待处理`
          : failed > 0
            ? `${failed} 条失败投递`
            : "服务可连接";
  return (
    <FactoryDetailsPanel
      title="检索投影运行状态"
      reveal={reveal}
      summary={
        <StatusBadge
          value={error || unavailable ? "failed" : failed > 0 || dead > 0 ? "warning" : "unknown"}
          label={summary}
        />
      }
    >
      <p>OpenSearch 集群、别名和投递队列来自服务状态；服务可连接不等于全部投递成功。</p>
      {error ? <ErrorState message="检索投影状态读取失败" retry={onRetry} /> : null}
      {pending && !data ? <Spinner label="正在读取检索投影状态" /> : null}
      {data ? (
        <>
          {error ? <p className="field-help">上次读取的状态（非实时）</p> : null}
          <dl className="enterprise-tenant-details factory-projection-metrics">
            <div>
              <dt>集群</dt>
              <dd>{data.cluster_name ?? "未连接"}</dd>
            </div>
            <div>
              <dt>集群状态</dt>
              <dd>{data.cluster_status ?? (data.error ? "连接失败，请检查检索服务配置与网络" : "未披露")}</dd>
            </div>
            <div>
              <dt>版本</dt>
              <dd>{data.version ?? "未披露"}</dd>
            </div>
            <div>
              <dt>索引别名</dt>
              <dd>{Object.keys(data.aliases).length}</dd>
            </div>
            <div>
              <dt>待投递</dt>
              <dd>{data.deliveries.pending ?? 0}</dd>
            </div>
            <div>
              <dt>失败投递</dt>
              <dd>{failed}</dd>
            </div>
            <div>
              <dt>死信</dt>
              <dd>{dead}</dd>
            </div>
          </dl>
        </>
      ) : null}
    </FactoryDetailsPanel>
  );
}
