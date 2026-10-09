import type { UseQueryResult } from "@tanstack/react-query";
import { History } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../../components/common";
import type { KnowledgeVersion, KnowledgeVersionDiff } from "../../lib/contracts/knowledge";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { knowledgeMessages } from "../../lib/i18n/knowledge";
import { KnowledgeChangeList } from "./KnowledgeChangeList";

export function KnowledgeVersionHistory({
  versions,
  diff,
  activeVersion,
  onVersion,
}: {
  versions: UseQueryResult<KnowledgeVersion[], Error>;
  diff: UseQueryResult<KnowledgeVersionDiff, Error>;
  activeVersion: number;
  onVersion: (version: number) => void;
}) {
  const text = useMessages(knowledgeMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const factChanges = (added: number, removed: number) =>
    text("+{added} / -{removed} 事实", { added: number.format(added), removed: number.format(removed) });
  return (
    <section className="knowledge-history-section">
      <header>
        <History size={17} />
        <h3>{text("版本历史")}</h3>
      </header>
      {versions.isPending ? (
        <Spinner label={text("正在读取版本历史")} />
      ) : versions.error ? (
        <ErrorState
          message={versions.error instanceof Error ? versions.error.message : text("版本历史加载失败")}
          retry={() => void versions.refetch()}
        />
      ) : versions.data?.length ? (
        <div className="knowledge-history-grid">
          <ul className="knowledge-version-list" aria-label={text("专题版本")}>
            {versions.data.map((version) => (
              <li key={version.version_number}>
                <button
                  type="button"
                  className={activeVersion === version.version_number ? "active" : ""}
                  aria-current={activeVersion === version.version_number ? "true" : undefined}
                  onClick={() => onVersion(version.version_number)}
                >
                  <span>
                    <strong>v{version.version_number}</strong>
                    {version.is_current ? <small className="knowledge-current-label">{text("当前")}</small> : null}
                  </span>
                  <small>{formatDate(version.source_snapshot_at, true)}</small>
                  <em>{factChanges(version.added_fact_count, version.removed_fact_count)}</em>
                </button>
              </li>
            ))}
          </ul>
          <div className="knowledge-version-diff" aria-live="polite">
            {diff.isPending ? (
              <Spinner label={text("正在比对版本")} />
            ) : diff.error ? (
              <ErrorState
                message={diff.error instanceof Error ? diff.error.message : text("版本差异加载失败")}
                retry={() => void diff.refetch()}
              />
            ) : diff.data ? (
              <>
                <header>
                  <div>
                    <p className="eyebrow">{text("版本差异")}</p>
                    <h4>
                      {diff.data.from_version_number
                        ? `v${diff.data.from_version_number} → v${diff.data.to_version_number}`
                        : text("初始版本 v{version}", { version: diff.data.to_version_number })}
                    </h4>
                  </div>
                  <span>{factChanges(diff.data.added_fact_count, diff.data.removed_fact_count)}</span>
                </header>
                {!diff.data.added_fact_count &&
                !diff.data.removed_fact_count &&
                !diff.data.added_source_count &&
                !diff.data.removed_source_count ? (
                  <EmptyState title={text("与上一版本无内容差异")} />
                ) : (
                  <>
                    <KnowledgeChangeList diff={diff.data} kind="added" />
                    <KnowledgeChangeList diff={diff.data} kind="removed" />
                    {diff.data.truncated ? (
                      <p className="inline-warning">{text("差异过多，当前仅展示每类前 100 条。")}</p>
                    ) : null}
                  </>
                )}
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <EmptyState title={text("尚无版本历史")} />
      )}
    </section>
  );
}
