import { useLocale } from "../lib/i18n";
import { sourceMetadataText as t } from "../lib/i18n/sourceMetadata";
import { KnowledgeStructuredValue } from "../views/knowledge/KnowledgeStructuredValue";
import "../styles/source-metadata.css";

/** Compact first view, with every original nested value still available verbatim. */
export function SourceMetadata({ details }: { details: Record<string, unknown> }) {
  useLocale();
  if (!Object.keys(details).length) return <p>{t("未披露")}</p>;
  return (
    <section className="source-metadata">
      <h3>{t("补充信息")}</h3>
      <KnowledgeStructuredValue value={details} />
      <details>
        <summary>{t("完整补充信息")}</summary>
        <section aria-label={t("完整原始补充信息")}>
          <pre>{JSON.stringify(details, null, 2)}</pre>
        </section>
      </details>
    </section>
  );
}
