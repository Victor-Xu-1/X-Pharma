import { Download } from "lucide-react";
import { useId } from "react";
import { EmptyState } from "../../components/common";
import type { EnvironmentInstallPlanRead, EnvironmentRead } from "../../lib/generated";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { environmentSourceText } from "../../lib/i18n/environment";
import { environmentInstallationMessages } from "../../lib/i18n/environmentInstallation";
import type { useEnvironmentInstallation } from "./useEnvironmentInstallation";

function downloadPlan(plan: EnvironmentInstallPlanRead) {
  const url = URL.createObjectURL(new Blob([`${JSON.stringify(plan, null, 2)}\n`], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `X-Pharma-install-${plan.recipe_id}-${plan.plan_id.slice(0, 12)}.json`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function EnvironmentInstallationPanel({
  environment,
  installation,
}: {
  environment: EnvironmentRead;
  installation: ReturnType<typeof useEnvironmentInstallation>;
}) {
  const text = useMessages(environmentInstallationMessages);
  const helpPrefix = useId();
  const {
    recipe,
    offline,
    plan,
    mutation,
    available,
    selectedRecipe,
    supported,
    selectRecipe,
    selectOffline,
    prepare,
  } = installation;
  return (
    <section className="environment-installation" aria-labelledby="environment-install-title">
      <header>
        <h2 id="environment-install-title">{text("受控安装与修复")}</h2>
        <p>{text("只安装本项目的锁定依赖。网页生成计划；主机侧明确确认后执行，不重启 WSL、不停止其他项目。")}</p>
      </header>
      <fieldset className="environment-recipes">
        <legend>{text("选择安装范围")}</legend>
        {!environment.recipes.length ? (
          <EmptyState title={text("暂无安装范围")} detail={text("当前没有可用配方；刷新状态后再检查。")} />
        ) : null}
        {environment.recipes.map((item) => (
          <label key={item.id}>
            <input
              type="radio"
              name="environment-recipe"
              value={item.id}
              checked={recipe === item.id}
              disabled={mutation.isPending}
              aria-label={environmentSourceText(item.label)}
              aria-describedby={`${helpPrefix}-${item.id}-description ${helpPrefix}-${item.id}-prerequisites`}
              onChange={() => selectRecipe(item.id)}
            />
            <span>
              <strong>{environmentSourceText(item.label)}</strong>
              <span className="cell-subtitle" id={`${helpPrefix}-${item.id}-description`}>
                {environmentSourceText(item.description)}
              </span>
              <span className="cell-subtitle" id={`${helpPrefix}-${item.id}-prerequisites`}>
                {text("前提：{items}", {
                  items: item.prerequisites.join(formattingLocale() === "en-US" ? ", " : "、"),
                })}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="environment-offline">
        <input
          type="checkbox"
          checked={offline}
          disabled={mutation.isPending}
          onChange={(event) => selectOffline(event.target.checked)}
        />
        {text("仅使用离线缓存（缺失时失败，不自动联网）")}
      </label>
      {!available ? (
        <p className="muted-text" role="status">
          {environment.host_status !== "current"
            ? text("先在主机侧检测并接入有效报告。")
            : text("源码有未提交变更；请使用干净版本后重新检测。")}
        </p>
      ) : null}
      {!selectedRecipe && environment.recipes.length ? (
        <p role="status">{text("请选择当前提供的安装范围。")}</p>
      ) : !supported ? (
        <p role="status">{text("该范围不支持离线缓存。请选择其他范围，或明确取消离线限制。")}</p>
      ) : null}
      <button
        className="primary-button"
        type="button"
        onClick={() => void prepare()}
        disabled={!available || !supported || mutation.isPending}
      >
        {mutation.isPending ? text("正在生成…") : text("生成安装计划")}
      </button>
      {mutation.isError ? (
        <p className="form-error" role="alert">
          {environmentSourceText(mutation.error.message)}
        </p>
      ) : null}
      {plan ? (
        <section className="environment-plan" aria-label={text("已生成的安装计划")}>
          <h3>{text("安装计划已生成，尚未执行")}</h3>
          <p>
            {text("模式：{mode} · 绑定源码 {revision} · 计划 {id}", {
              mode: plan.offline ? text("离线") : text("允许联网"),
              revision: plan.revision.slice(0, 12),
              id: plan.plan_id.slice(0, 12),
            })}
          </p>
          <ul>
            {plan.commands.map((command) => (
              <li key={command.join("\u001f")}>
                <code>{command.join(" ")}</code>
              </li>
            ))}
          </ul>
          <button className="secondary-button" type="button" onClick={() => downloadPlan(plan)}>
            <Download size={15} aria-hidden="true" />
            {text("下载安装计划")}
          </button>
          <p>{text("将计划保存到 E 盘，由本地主机运行以下命令。执行器会复查版本、锁文件和有效期，并记录真实结果。")}</p>
          <pre>
            <code>
              pharma-environment install --repository /srv/wsl/projects/x-pharma --plan
              /srv/wsl/data/x-pharma-environment/plan.json --execute
            </code>
          </pre>
        </section>
      ) : null}
      <details>
        <summary>{text("如何接入主机检测报告")}</summary>
        <p>{text("由本地运维运行只读检测，并将报告目录只读挂载给网关；不向网页暴露 Docker socket 或私人配置。")}</p>
        <pre>
          <code>
            pharma-environment inspect --repository /srv/wsl/projects/x-pharma --output
            /srv/wsl/data/x-pharma-environment/evidence/environment/host.json
          </code>
        </pre>
      </details>
    </section>
  );
}
