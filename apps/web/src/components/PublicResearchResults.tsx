import type { PublicResearchResponse } from "../lib/generated";

const statusLabels = { available: "可读取", empty: "当前范围未命中", unavailable: "暂不可用" };

export function PublicResearchResults({ response }: { response: PublicResearchResponse }) {
  return (
    <section aria-label="公开调研结果">
      <p className="inline-feedback" role="status">
        已查询：{response.query} · {new Date(response.observed_at).toLocaleString()} ·
        公开元数据，未自动入库或核验为事实。
      </p>
      {response.results.map((source, index) => (
        <details className="advanced-filters" key={source.topic} open={index === 0}>
          <summary>
            {source.provider} · <span>{statusLabels[source.status]}</span>
            {source.total !== null && source.total !== undefined ? (
              <span>来源命中 {source.total.toLocaleString()} 条</span>
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
                    {record.published_on ? `来源日期：${record.published_on} · ` : "来源日期未提供 · "}
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
              到来源继续检索
            </a>
          </p>
          <p className="entity-search-aliases">{source.license_notice}</p>
        </details>
      ))}
    </section>
  );
}
