import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { prepareEnvironmentPlan } from "../../lib/contracts/environment";
import type { EnvironmentInstallPlanRead, EnvironmentPlanCreate, EnvironmentRead } from "../../lib/generated";

function downloadPlan(plan: EnvironmentInstallPlanRead) {
  const url = URL.createObjectURL(new Blob([`${JSON.stringify(plan, null, 2)}\n`], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `X-Pharma-install-${plan.recipe_id}-${plan.plan_id.slice(0, 12)}.json`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function EnvironmentInstallationPanel({ environment }: { environment: EnvironmentRead }) {
  const [recipe, setRecipe] = useState<EnvironmentPlanCreate["recipe_id"]>("frontend-dependencies");
  const [offline, setOffline] = useState(true);
  const [plan, setPlan] = useState<EnvironmentInstallPlanRead | null>(null);
  const mutation = useMutation({
    mutationFn: (request: EnvironmentPlanCreate) => prepareEnvironmentPlan(request),
    retry: false,
  });
  const available = environment.host_status === "current" && environment.host?.clean_source;
  async function prepare() {
    setPlan(null);
    try {
      setPlan(await mutation.mutateAsync({ recipe_id: recipe, offline }));
    } catch {
      /* Error stays visible in the mutation state; no fallback or execution. */
    }
  }
  return (
    <section className="environment-installation" aria-labelledby="environment-install-title">
      <header>
        <h2 id="environment-install-title">受控安装与修复</h2>
        <p>只安装本项目的锁定依赖。网页生成计划；主机侧明确确认后执行，不重启 WSL、不停止其他项目。</p>
      </header>
      <fieldset className="environment-recipes">
        <legend>选择安装范围</legend>
        {environment.recipes.map((item) => (
          <label key={item.id}>
            <input
              type="radio"
              name="environment-recipe"
              value={item.id}
              checked={recipe === item.id}
              onChange={() => {
                setRecipe(item.id);
                setPlan(null);
                mutation.reset();
              }}
            />
            <span>
              <strong>{item.label}</strong>
              <span className="cell-subtitle">{item.description}</span>
              <span className="cell-subtitle">前提：{item.prerequisites.join("、")}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="environment-offline">
        <input
          type="checkbox"
          checked={offline}
          onChange={(event) => {
            setOffline(event.target.checked);
            setPlan(null);
            mutation.reset();
          }}
        />
        仅使用离线缓存（缺失时失败，不自动联网）
      </label>
      {!available ? (
        <p className="muted-text" role="status">
          {environment.host_status !== "current"
            ? "先在主机侧检测并接入有效报告。"
            : "源码有未提交变更；请使用干净版本后重新检测。"}
        </p>
      ) : null}
      <button
        className="primary-button"
        type="button"
        onClick={() => void prepare()}
        disabled={!available || mutation.isPending}
      >
        {mutation.isPending ? "正在生成…" : "生成安装计划"}
      </button>
      {mutation.isError ? (
        <p className="form-error" role="alert">
          {mutation.error.message}
        </p>
      ) : null}
      {plan ? (
        <section className="environment-plan" aria-label="已生成的安装计划">
          <h3>安装计划已生成，尚未执行</h3>
          <p>
            模式：{plan.offline ? "离线" : "允许联网"} · 绑定源码 {plan.revision.slice(0, 12)} · 计划{" "}
            {plan.plan_id.slice(0, 12)}
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
            下载安装计划
          </button>
          <p>将计划保存到 E 盘，由本地主机运行以下命令。执行器会复查版本、锁文件和有效期，并记录真实结果。</p>
          <pre>
            <code>
              pharma-environment install --repository /srv/wsl/projects/x-pharma --plan
              /srv/wsl/data/x-pharma-environment/plan.json --execute
            </code>
          </pre>
        </section>
      ) : null}
      <details>
        <summary>如何接入主机检测报告</summary>
        <p>由本地运维运行只读检测，并将报告目录只读挂载给网关；不向网页暴露 Docker socket 或私人配置。</p>
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
