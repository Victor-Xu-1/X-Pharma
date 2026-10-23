import { formatDate, StatusBadge } from "../../components/common";
import type { GovernanceRun } from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import { governanceRunText as t } from "../../lib/i18n/governanceRuns";

export function GovernanceRunDetail({ run }: { run: GovernanceRun | null }) {
  useLocale();
  if (!run) return <article className="review-detail" />;
  const totalTokens = (run.input_tokens ?? 0) + (run.output_tokens ?? 0);
  const tokenLabel =
    run.input_tokens === null && run.output_tokens === null
      ? t("未上报")
      : run.input_tokens === null || run.output_tokens === null
        ? t("已上报 Token（不完整）：{tokens}", { tokens: totalTokens })
        : String(totalTokens);
  return (
    <article className="review-detail">
      <header>
        <div>
          <h2>{run.source_file_name}</h2>
          <p>{run.source_logical_path}</p>
        </div>
        <StatusBadge value={run.status} />
      </header>
      <section>
        <h3>{t("执行配置")}</h3>
        <dl className="review-source governance-run-metadata">
          <div>
            <dt>{t("模型")}</dt>
            <dd>
              {run.model_provider} / {run.model_name}
            </dd>
          </div>
          <div>
            <dt>Schema</dt>
            <dd>
              {run.schema_name} {run.schema_version}
            </dd>
          </div>
          <div>
            <dt>{t("策略状态")}</dt>
            <dd>{t(run.policy_current ? "当前策略" : "历史策略")}</dd>
          </div>
          <div>
            <dt>{t("Token / 成本")}</dt>
            <dd>
              {tokenLabel}
              {run.estimated_cost !== null ? ` / ${run.estimated_cost}` : ""}
            </dd>
          </div>
          <div>
            <dt>{t("开始时间")}</dt>
            <dd>{formatDate(run.started_at ?? run.created_at, true)}</dd>
          </div>
          <div>
            <dt>{t("完成时间")}</dt>
            <dd>{run.completed_at ? formatDate(run.completed_at, true) : t("尚未完成")}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>{t("可审计指纹")}</h3>
        <dl className="governance-fingerprints">
          <div>
            <dt>Source</dt>
            <dd>
              <code>{run.source_content_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Input</dt>
            <dd>
              <code>{run.input_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Prompt</dt>
            <dd>
              <code>{run.prompt_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>
              <code>{run.policy_sha256}</code>
            </dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>{t("校验结果")}</h3>
        {run.validation_errors.length ? (
          <pre className="json-preview compact">{JSON.stringify(run.validation_errors, null, 2)}</pre>
        ) : (
          <p className="muted">{t("未记录结构化校验错误")}</p>
        )}
      </section>
    </article>
  );
}
