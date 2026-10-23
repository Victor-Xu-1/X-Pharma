import { Check, RotateCcw } from "lucide-react";
import { ErrorState, Spinner, StatusBadge } from "../../components/common";
import { governanceLabel } from "../../lib/governancePresentation";
import { governancePublicationText as t } from "../../lib/i18n/governancePublication";
import { completePublicationMembership } from "./publicationValidation";
import type { PublicationBatchController } from "./usePublicationBatch";

export function PublicationPreview({ batch }: { batch: PublicationBatchController }) {
  const record = batch.detail;
  return (
    <section className="publication-preview" aria-labelledby="publication-preview-title">
      <header>
        <h3 id="publication-preview-title">{t("固定预览")}</h3>
        {batch.activeId ? (
          <button
            className="icon-button"
            type="button"
            aria-label={t("刷新批次明细")}
            disabled={batch.busy || batch.activeBatch.isFetching}
            onClick={() => void batch.activeBatch.refetch()}
          >
            <RotateCcw size={15} />
          </button>
        ) : null}
      </header>
      {batch.activeBatch.isFetching ? <Spinner label={t("正在读取批次明细")} /> : null}
      {batch.detailError ? (
        <ErrorState message={batch.detailError} retry={() => void batch.activeBatch.refetch()} />
      ) : null}
      {record && batch.detailError ? (
        <p role="status" className="field-help">
          {t("刷新失败；以下为上次成功读取的记录，恢复前不能提交。")}
        </p>
      ) : null}
      {record ? (
        <>
          <dl>
            <div>
              <dt>{t("操作")}</dt>
              <dd>{t(record.operation === "publish" ? "批次发布" : "批次撤回")}</dd>
            </div>
            <div>
              <dt>{t("状态")}</dt>
              <dd>
                <StatusBadge value={record.status} />
              </dd>
            </div>
            <div>
              <dt>{t("阻塞项")}</dt>
              <dd>{record.blocked_count}</dd>
            </div>
          </dl>
          <p className="field-help">
            {t("原始审核依据")}: {record.reason ?? "—"}
          </p>
          <details className="publication-fingerprint">
            <summary>{t("预览指纹")}</summary>
            <code>{record.preview_sha256}</code>
          </details>
          <div className="publication-preview-items">
            {(record.items ?? []).map((item) => (
              <article key={item.id}>
                <span>
                  <strong>
                    {typeof item.snapshot.fact_kind === "string"
                      ? governanceLabel(item.snapshot.fact_kind)
                      : item.staged_fact_id}
                  </strong>
                  <StatusBadge value={item.outcome} />
                </span>
                {item.blockers.map((blocker) => (
                  <p key={JSON.stringify(blocker)}>
                    {typeof blocker.code === "string" ? blocker.code : JSON.stringify(blocker)}
                  </p>
                ))}
              </article>
            ))}
          </div>
          {!completePublicationMembership(record) ? <p className="field-help">{t("预览明细未完整返回")}</p> : null}
          {record.status === "previewed" ? (
            <button
              className="primary-button"
              type="button"
              disabled={
                batch.busy || !batch.detailReady || record.blocked_count > 0 || !completePublicationMembership(record)
              }
              onClick={batch.commit}
            >
              <Check size={16} />
              {t(record.operation === "publish" ? "原子提交发布" : "原子提交撤回")}
            </button>
          ) : null}
          {record.status === "committed" && record.operation === "publish" ? (
            <button
              className="danger-button"
              type="button"
              disabled={batch.busy || !batch.detailReady || !completePublicationMembership(record)}
              onClick={batch.previewWithdrawal}
            >
              <RotateCcw size={16} />
              {t("基于此批次生成撤回预览")}
            </button>
          ) : null}
        </>
      ) : !batch.detailError && !batch.activeBatch.isFetching ? (
        <p className="field-help">{t("选择历史批次或生成新预览以查看逐项结果")}</p>
      ) : null}
      {batch.error && !batch.confirmRebuild ? (
        <p className="form-error" role="alert">
          {batch.error}
        </p>
      ) : null}
    </section>
  );
}
