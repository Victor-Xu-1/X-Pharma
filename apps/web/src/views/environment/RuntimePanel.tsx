import { formatDate } from "../../components/common";
import { dependencyReadinessLabels, environmentReadiness } from "../../lib/environmentReadiness";
import type { EnvironmentRead } from "../../lib/generated";
import { EnvironmentProbeTable } from "./ProbeTable";

export function EnvironmentRuntimePanel({ environment }: { environment: EnvironmentRead }) {
  const readiness = environmentReadiness(environment);
  return (
    <>
      <section aria-label="依赖就绪概览">
        <h2>依赖就绪概览 · {dependencyReadinessLabels[readiness.overall]}</h2>
        <p>
          网关：{dependencyReadinessLabels[readiness.gateway]} · 项目环境：
          {dependencyReadinessLabels[readiness.host]}
        </p>
        {readiness.issues.length ? (
          <p>
            {readiness.issues.length} 项需处理：{readiness.issues.map((probe) => probe.label).join("、")}
          </p>
        ) : null}
        <p>
          仅汇总网关与所报项目依赖，不代表完整离线包或生产环境已验收。数据库、采集、身份及恢复需独立验证。
          未声明明确版本要求时，不判定为兼容。
        </p>
        <p>{environment.host_detail}</p>
        {environment.host ? (
          <p>
            主机检测 {formatDate(environment.host.generated_at, true)} · 源码 {environment.host.revision.slice(0, 12)} ·{" "}
            {environment.host.clean_source ? "源码干净" : "存在未提交变更"} · 可用空间{" "}
            {(environment.host.disk_free_bytes / 1024 ** 3).toFixed(1)} GiB
          </p>
        ) : null}
      </section>
      <details open={readiness.gateway !== "ready"}>
        <summary>查看网关依赖明细</summary>
        <p>网关进程的实际版本，不代表主机或其他容器已经健康。</p>
        <EnvironmentProbeTable probes={environment.runtime} label="网关依赖版本" />
      </details>
      {environment.host ? (
        <details open={readiness.host !== "ready"}>
          <summary>查看主机与项目依赖明细</summary>
          <EnvironmentProbeTable probes={environment.host.probes} label="主机依赖版本" />
          {environment.host.latest_install ? (
            <p role="status">
              最近安装：{environment.host.latest_install.recipe_id} ·{" "}
              {environment.host.latest_install.status === "succeeded"
                ? "成功"
                : environment.host.latest_install.status === "running"
                  ? "执行中"
                  : "失败"}{" "}
              · {environment.host.latest_install.detail} ·{" "}
              {environment.host.latest_install.revision
                ? `安装时源码 ${environment.host.latest_install.revision.slice(0, 12)}`
                : "旧记录未绑定源码，不能作为当前源码的安装证明"}
            </p>
          ) : null}
        </details>
      ) : (
        <p role="status">尚无有效的主机报告。可在“安装与修复”查看接入步骤。</p>
      )}
    </>
  );
}
