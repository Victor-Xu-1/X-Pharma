import type { PublicResearchResponse } from "../lib/generated";
import { formattingLocale, useMessages } from "../lib/i18n";
import { publicResearchMessages } from "../lib/i18n/publicResearch";
import { formatDate } from "./common";

const statusLabels = { available: "可读取", empty: "当前范围未命中", unavailable: "暂不可用" } as const;

export function PublicResearchResults({ response }: { response: PublicResearchResponse }) {
  const t = useMessages(publicResearchMessages);
  return (
    <section aria-label={t("公开调研结果")}>
      <p className="inline-feedback" role="status">
        {t("已查询：{query} · {observed} · 公开元数据，未自动入库或核验为事实。", {
          query: response.query,
          observed: formatDate(response.observed_at, true),
        })}
      </p>
      {response.results.map((source, index) => (
        <details className="advanced-filters" key={source.topic} open={index === 0}>
          <summary>
            {source.provider} · <span>{t(statusLabels[source.status])}</span>
            {source.total !== null && source.total !== undefined ? (
              <span>{t("来源命中 {count} 条", { count: source.total.toLocaleString(formattingLocale()) })}</span>
            ) : null}
          </summary>
          <p>{source.scope_note}</p>
          {source.warnings?.map((warning) => (
            <p className="inline-feedback" role="status" key={warning}>
              {warning}
            </p>
          ))}
          {source.status === "available" ? (
            <ol>
              {(source.records ?? []).map((record) => (
                <li className="company-profile-identity" key={record.record_id}>
                  <p>
                    <a href={record.url} target="_blank" rel="noreferrer noopener">
                      {record.title}
                    </a>
                  </p>
                  <p>
                    {record.published_on
                      ? t("来源日期：{date} · ", { date: record.published_on })
                      : t("来源日期未提供 · ")}
                    {record.record_id}
                  </p>
                  {Object.keys(record.fields ?? {}).length ? (
                    <p>
                      {Object.entries(record.fields ?? {})
                        .filter(([, value]) => value)
                        .map(([label, value]) => `${label}：${value}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : null}
          <p>
            <a href={source.source_query_url} target="_blank" rel="noreferrer noopener">
              {t("到来源继续检索")}
            </a>
          </p>
          <p className="entity-search-aliases">{source.license_notice}</p>
        </details>
      ))}
    </section>
  );
}
