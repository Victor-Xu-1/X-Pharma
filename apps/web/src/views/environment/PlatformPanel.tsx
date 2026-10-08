import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { PlatformOperationsRead } from "../../lib/generated";

export function queueCount(value: unknown, key: string): number {
  if (!value || typeof value !== "object") return 0;
  const count = (value as Record<string, unknown>)[key];
  return typeof count === "number" ? count : 0;
}

export function deliveryDeadCount(value: unknown): number {
  if (!value || typeof value !== "object") return 0;
  return Object.values(value as Record<string, unknown>).reduce<number>(
    (total, states) => total + queueCount(states, "dead"),
    0,
  );
}

export function PlatformOperationsPanel({ platform }: { platform: PlatformOperationsRead }) {
  const ingestion = platform.queues.ingestion;
  const outbox = platform.queues.outbox;
  const governance = platform.queues.governance;
  const deliveries = platform.queues.deliveries;
  const queueMetrics = [
    ["待运行入库", queueCount(ingestion, "pending")],
    ["运行中入库", queueCount(ingestion, "running")],
    ["过期心跳", queueCount(ingestion, "stale")],
    ["待发布事件", queueCount(outbox, "pending")],
    ["失败事件", queueCount(outbox, "failed")],
    ["投影死信", deliveryDeadCount(deliveries)],
    ["待审核事实", queueCount(governance, "review_pending")],
  ] as const;

  return (
    <div className="platform-operations">
      <section aria-labelledby="platform-services-title">
        <header>
          <div>
            <h2 id="platform-services-title">服务与责任边界</h2>
            <p>应用内信号与外部部署探针分开呈现；没有生产遥测时不会显示为已达标。</p>
          </div>
          <span className="cell-subtitle">快照 {formatDate(platform.generated_at, true)}</span>
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="平台服务状态明细">
          <table aria-label="平台服务状态">
            <thead>
              <tr>
                <th>服务</th>
                <th>负责人</th>
                <th>状态</th>
                <th>判定依据</th>
              </tr>
            </thead>
            <tbody>
              {platform.services.map((service) => (
                <tr key={service.service_id}>
                  <td className="mono-value">{service.service_id}</td>
                  <td>{service.owner}</td>
                  <td>
                    <StatusBadge value={service.status} />
                    <span className="cell-subtitle">
                      配置：{service.enabled === null ? "由部署探针确认" : service.enabled ? "已启用" : "未启用"}
                    </span>
                    <span className="cell-subtitle">
                      存活：
                      {service.liveness === "observed"
                        ? "本次请求已验证"
                        : service.liveness === "unverified"
                          ? "尚未探测"
                          : "不适用"}
                    </span>
                    <span className="cell-subtitle">
                      队列：
                      {service.queue_status === "healthy"
                        ? "未发现积压故障"
                        : service.queue_status === "degraded"
                          ? "存在故障"
                          : "不适用"}
                    </span>
                  </td>
                  <td>{service.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="platform-queues-title">
        <header>
          <div>
            <h2 id="platform-queues-title">队列、工作流与模型预算</h2>
            <p>计数直接来自当前租户权威库；模型统计仅汇总远程 API 运行记录。</p>
          </div>
        </header>
        <dl className="platform-queue-metrics">
          {queueMetrics.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="platform-runtime-grid">
          <dl>
            <div>
              <dt>工作流引擎</dt>
              <dd>{platform.workflow.engine.toUpperCase()}</dd>
            </div>
            <div>
              <dt>任务队列</dt>
              <dd className="mono-value">{platform.workflow.task_queue}</dd>
            </div>
            <div>
              <dt>最大并发活动</dt>
              <dd>{platform.workflow.max_concurrent_activities}</dd>
            </div>
          </dl>
          <dl>
            <div>
              <dt>24h 模型运行</dt>
              <dd>{platform.model_budget.run_count}</dd>
            </div>
            <div>
              <dt>输入 / 输出 token</dt>
              <dd>
                {platform.model_budget.input_tokens} / {platform.model_budget.output_tokens}
              </dd>
            </div>
            <div>
              <dt>估算成本 / 单文档上限</dt>
              <dd>
                {platform.model_budget.estimated_cost} / {platform.model_budget.max_document_cost}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section aria-labelledby="platform-slo-title">
        <header>
          <div>
            <h2 id="platform-slo-title">SLO 与告警契约</h2>
            <p>目标来自版本化运维契约；达标结论必须由目标环境集中遥测证据给出。</p>
          </div>
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="平台 SLO 明细">
          <table aria-label="平台 SLO">
            <thead>
              <tr>
                <th>SLO</th>
                <th>服务</th>
                <th>指标</th>
                <th>目标 / 窗口</th>
                <th>评估</th>
              </tr>
            </thead>
            <tbody>
              {platform.slos.map((slo) => (
                <tr key={slo.id}>
                  <td>{slo.id}</td>
                  <td className="mono-value">{slo.service}</td>
                  <td>
                    {slo.metric}
                    <span className="cell-subtitle">{slo.measurement}</span>
                  </td>
                  <td>
                    {slo.target} / {slo.window}
                  </td>
                  <td>
                    <StatusBadge value="external" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="platform-evidence-title">
        <header>
          <div>
            <h2 id="platform-evidence-title">迁移、备份恢复与发布证据</h2>
            <p>只接受预定义位置的机器报告；缺失、损坏或未挂载都会显式阻断发布结论。</p>
          </div>
        </header>
        <div className="platform-migration">
          <span>数据库迁移</span>
          <StatusBadge value={platform.migration.status} />
          <code>{platform.migration.current_revision ?? "unknown"}</code>
          <span className="cell-subtitle">目标 {platform.migration.expected_revision ?? "unknown"}</span>
        </div>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="平台发布证据明细">
          <table aria-label="平台发布证据">
            <thead>
              <tr>
                <th>证据类别</th>
                <th>状态</th>
                <th>制品</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              {platform.evidence.map((evidence) => (
                <tr key={evidence.category}>
                  <td>{evidence.category}</td>
                  <td>
                    <StatusBadge value={evidence.status} />
                  </td>
                  <td className="mono-value">{evidence.artifact}</td>
                  <td>
                    {evidence.detail}
                    {evidence.sha256 ? (
                      <span className="cell-subtitle">sha256 {evidence.sha256.slice(0, 12)}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="platform-events-title">
        <header>
          <div>
            <h2 id="platform-events-title">最近平台审计事件</h2>
            <p>保留请求关联 ID，便于从人员操作追踪到服务端日志和发布证据。</p>
          </div>
        </header>
        {platform.recent_events.length ? (
          <ScrollableTableRegion className="enterprise-table" ariaLabel="最近平台审计事件明细">
            <table aria-label="最近平台审计事件">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作</th>
                  <th>资源</th>
                  <th>结果</th>
                  <th>请求 ID</th>
                </tr>
              </thead>
              <tbody>
                {platform.recent_events.map((event) => (
                  <tr key={event.id}>
                    <td>{formatDate(event.occurred_at, true)}</td>
                    <td>{event.action}</td>
                    <td>{event.resource_type}</td>
                    <td>
                      <StatusBadge value={event.outcome} />
                    </td>
                    <td className="mono-value">{event.request_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title="暂无审计事件" detail="当前租户还没有可显示的平台操作记录。" />
        )}
      </section>
    </div>
  );
}
