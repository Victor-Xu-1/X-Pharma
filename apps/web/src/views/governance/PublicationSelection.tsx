import { ClipboardCheck } from "lucide-react";
import { StatusBadge } from "../../components/common";
import type { StagedFact } from "../../lib/contracts/governance";
import { reviewFactTitle } from "../../lib/governancePresentation";
import { governancePublicationText as t } from "../../lib/i18n/governancePublication";
import type { PublicationBatchController } from "./usePublicationBatch";

export function PublicationSelection({ facts, batch }: { facts: StagedFact[]; batch: PublicationBatchController }) {
  return (
    <section className="publication-selection" aria-labelledby="publication-selection-title">
      <header>
        <div>
          <h3 id="publication-selection-title">{t("待审事实选择")}</h3>
          <p>{t("先生成固定预览，再按同一 preview hash 原子提交。")}</p>
        </div>
        <button
          type="button"
          className="text-button"
          disabled={batch.busy || !batch.ready || !facts.length}
          onClick={batch.toggleAll}
        >
          {t(batch.selectedIds.length === facts.length && facts.length ? "取消全选" : "全选")}
        </button>
      </header>
      {facts.length ? (
        <div className="publication-fact-list">
          {facts.map((fact) => (
            <label key={fact.id}>
              <input
                type="checkbox"
                checked={batch.selectedIds.includes(fact.id)}
                disabled={batch.busy || !batch.ready}
                onChange={(event) => batch.select(fact.id, event.target.checked)}
              />
              <span>
                <strong>{reviewFactTitle(fact)}</strong>
                <small className="mono-cell">{fact.source_locator ?? fact.id}</small>
                <small title={fact.source_quote}>{fact.source_quote}</small>
              </span>
              <StatusBadge value={fact.status} />
            </label>
          ))}
        </div>
      ) : (
        <p className="field-help">{t("当前没有可加入发布批次的待审事实")}</p>
      )}
      {batch.missing.length ? (
        <p role="status" className="field-help">
          {t("{count} 个已选事实不再位于当前审核队列", { count: batch.missing.length })}
        </p>
      ) : null}
      <label className="publication-reason">
        <span>{t("批次审核依据")}</span>
        <textarea
          aria-label={t("批次审核依据")}
          rows={3}
          maxLength={4000}
          value={batch.reason}
          disabled={batch.busy}
          onChange={(event) => batch.changeReason(event.target.value)}
        />
      </label>
      <button
        className="primary-button"
        type="button"
        disabled={batch.busy || !batch.ready || Boolean(batch.missing.length)}
        onClick={batch.previewPublish}
      >
        <ClipboardCheck size={16} />
        {t("生成发布预览 ({count})", { count: batch.selectedIds.length })}
      </button>
    </section>
  );
}
