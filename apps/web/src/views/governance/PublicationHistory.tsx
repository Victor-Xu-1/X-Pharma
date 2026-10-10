import { RotateCcw } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { governancePublicationText as t } from "../../lib/i18n/governancePublication";
import type { PublicationBatchController } from "./usePublicationBatch";

export function PublicationHistory({ batch }: { batch: PublicationBatchController }) {
  return (
    <section className="publication-history" aria-labelledby="publication-history-title">
      <header>
        <h3 id="publication-history-title">{t("批次历史")}</h3>
        <button
          className="icon-button"
          type="button"
          title={t("刷新批次历史")}
          aria-label={t("刷新批次历史")}
          disabled={batch.busy || batch.batches.isFetching}
          onClick={() => void batch.batches.refetch()}
        >
          <RotateCcw size={15} />
        </button>
      </header>
      {batch.batches.isPending ? <Spinner label={t("正在读取发布批次")} /> : null}
      {batch.batches.error instanceof Error ? (
        <ErrorState message={batch.batches.error.message} retry={() => void batch.batches.refetch()} />
      ) : null}
      {!batch.batches.isPending && !batch.batches.error && !batch.history?.length ? (
        <p className="field-help">{t("当前没有批次历史")}</p>
      ) : null}
      <div className="publication-batch-list">
        {(batch.history ?? []).map((record) => (
          <button
            key={record.id}
            type="button"
            disabled={batch.busy}
            className={batch.activeId === record.id ? "active" : ""}
            aria-pressed={batch.activeId === record.id}
            onClick={() => batch.selectBatch(record.id)}
          >
            <span>
              <strong>{t(record.operation === "publish" ? "发布" : "撤回")}</strong>
              <StatusBadge value={record.status} />
            </span>
            <small>
              {record.expected_count === 1 ? t("1 项") : t("{count} 项", { count: record.expected_count })} ·{" "}
              {formatDate(record.created_at, true)}
            </small>
          </button>
        ))}
      </div>
    </section>
  );
}
