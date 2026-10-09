import { formatDate } from "../../components/common";
import { dependencyReadinessLabels, environmentReadiness } from "../../lib/environmentReadiness";
import type { EnvironmentRead } from "../../lib/generated";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { environmentMessages, environmentSourceText } from "../../lib/i18n/environment";
import { EnvironmentProbeTable } from "./ProbeTable";

export function EnvironmentRuntimePanel({ environment }: { environment: EnvironmentRead }) {
  const text = useMessages(environmentMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const readiness = environmentReadiness(environment);
  return (
    <>
      <section className="environment-readiness" aria-label={text("依赖就绪概览")}>
        <h2>
          {text("依赖就绪概览")} · {text(dependencyReadinessLabels[readiness.overall])}
        </h2>
        <dl className="environment-readiness-grid">
          <div>
            <dt>{text("应用网关")}</dt>
            <dd>{text(dependencyReadinessLabels[readiness.gateway])}</dd>
          </div>
          <div>
            <dt>{text("项目环境")}</dt>
            <dd>{text(dependencyReadinessLabels[readiness.host])}</dd>
          </div>
        </dl>
        {readiness.issues.length ? (
          <p>
            {text("{count} 项需处理：{labels}", {
              count: number.format(readiness.issues.length),
              labels: readiness.issues
                .map((probe) => environmentSourceText(probe.label))
                .join(formattingLocale() === "en-US" ? ", " : "、"),
            })}
          </p>
        ) : null}
        <p>
          {text(
            "仅汇总网关与所报项目依赖，不代表完整离线包或生产环境已验收。数据库、采集、身份及恢复需独立验证。未声明明确版本要求时，不判定为兼容。",
          )}
        </p>
        <p>{environmentSourceText(environment.host_detail)}</p>
        {environment.host ? (
          <p>
            {text("主机检测 {time} · 源码 {revision} · {state} · 可用空间 {space} GiB", {
              time: formatDate(environment.host.generated_at, true),
              revision: environment.host.revision.slice(0, 12),
              state: environment.host.clean_source ? text("源码干净") : text("存在未提交变更"),
              space: new Intl.NumberFormat(formattingLocale(), {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              }).format(environment.host.disk_free_bytes / 1024 ** 3),
            })}
          </p>
        ) : null}
      </section>
      <details className="environment-disclosure" open={readiness.gateway !== "ready"}>
        <summary>{text("查看网关依赖明细")}</summary>
        <p>{text("网关进程的实际版本，不代表主机或其他容器已经健康。")}</p>
        <EnvironmentProbeTable probes={environment.runtime} label={text("网关依赖版本")} />
      </details>
      {environment.host ? (
        <details className="environment-disclosure" open={readiness.host !== "ready"}>
          <summary>{text("查看主机与项目依赖明细")}</summary>
          <EnvironmentProbeTable probes={environment.host.probes} label={text("主机依赖版本")} />
          {environment.host.latest_install ? (
            <p role="status">
              {text("最近安装：{recipe} · {status} · {detail} · {revision}", {
                recipe: environment.host.latest_install.recipe_id,
                status:
                  environment.host.latest_install.status === "succeeded"
                    ? text("成功")
                    : environment.host.latest_install.status === "running"
                      ? text("执行中")
                      : text("失败"),
                detail: environmentSourceText(environment.host.latest_install.detail),
                revision: environment.host.latest_install.revision
                  ? text("安装时源码 {revision}", { revision: environment.host.latest_install.revision.slice(0, 12) })
                  : text("旧记录未绑定源码，不能作为当前源码的安装证明"),
              })}
            </p>
          ) : null}
        </details>
      ) : (
        <p role="status">{text("尚无有效的主机报告。可在“安装与修复”查看接入步骤。")}</p>
      )}
    </>
  );
}
