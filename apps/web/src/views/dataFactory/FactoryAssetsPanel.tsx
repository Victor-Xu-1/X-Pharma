import { ChevronLeft, ChevronRight, Eye, FileText } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { SourceAssetPageRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";

/** Presentation only: the root owns the query, permission boundary and pagination. */
export function FactoryAssetsPanel({
  data,
  pending,
  refreshing,
  error,
  onRetry,
  onPageChange,
  onOpen,
}: {
  data: SourceAssetPageRead | undefined;
  pending: boolean;
  refreshing: boolean;
  error: Error | null;
  onRetry: () => void;
  onPageChange: (page: number) => void;
  onOpen: (id: string) => void;
}) {
  useLocale();
  const page = data ? Math.floor(data.offset / data.limit) : 0;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;
  return (
    <section aria-label={t("源对象与版本")}>
      <div className="section-header">
        <div>
          <h2>{t("源对象与版本")}</h2>
          <p>{t("只读查看来源路径、版本哈希、处理阶段、恶意文件结果和解析文本")}</p>
        </div>
      </div>
      {error ? (
        <>
          <ErrorState message={error.message} />
          <button className="secondary-button" type="button" disabled={refreshing} onClick={onRetry}>
            {t("重试源对象")}
          </button>
        </>
      ) : null}
      {pending && !data ? <Spinner label={t("正在读取源对象")} /> : null}
      {refreshing && data ? <Spinner label={t("正在刷新源对象")} /> : null}
      {data && error ? <p className="field-help">{t("上次读取的源对象（非实时）")}</p> : null}
      {data ? (
        data.items.length ? (
          <>
            <ScrollableTableRegion ariaLabel={t("源对象明细")}>
              <table>
                <thead>
                  <tr>
                    <th>{t("文件")}</th>
                    <th>{t("来源路径")}</th>
                    <th>{t("状态")}</th>
                    <th>{t("处理方式")}</th>
                    <th>{t("最近发现")}</th>
                    <th aria-label={t("操作")} />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((asset) => (
                    <tr key={asset.id}>
                      <td>{asset.file_name}</td>
                      <td className="mono-cell">{asset.logical_path}</td>
                      <td>
                        <StatusBadge value={asset.state} />
                      </td>
                      <td>
                        {asset.processing_mode === "parse"
                          ? t("真实解析")
                          : asset.processing_mode === "asset_only"
                            ? t("仅登记资产")
                            : asset.processing_mode}
                      </td>
                      <td>{formatDate(asset.last_seen_at, true)}</td>
                      <td>
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => onOpen(asset.id)}
                          title={t("查看版本")}
                          aria-label={t("查看 {name} 版本", { name: asset.file_name })}
                        >
                          <Eye size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollableTableRegion>
            <nav className="factory-run-pagination" aria-label={t("源对象分页")}>
              <span>
                {t("第 {page} / {pages} 页，共 {total} 个对象", {
                  page: page + 1,
                  pages: pageCount,
                  total: data.total,
                })}
              </span>
              <div>
                <button
                  className="icon-button"
                  type="button"
                  disabled={refreshing || page === 0}
                  onClick={() => onPageChange(Math.max(0, page - 1))}
                  aria-label={t("源对象上一页")}
                  title={t("上一页")}
                >
                  <ChevronLeft size={17} />
                </button>
                <button
                  className="icon-button"
                  type="button"
                  disabled={refreshing || page >= pageCount - 1}
                  onClick={() => onPageChange(Math.min(pageCount - 1, page + 1))}
                  aria-label={t("源对象下一页")}
                  title={t("下一页")}
                >
                  <ChevronRight size={17} />
                </button>
              </div>
            </nav>
          </>
        ) : !error ? (
          <div className="factory-run-empty">
            <FileText size={20} />
            <span>
              <strong>{t("暂无源对象")}</strong>
              <small>{t("自动数据源发现文件后，版本和解析状态会显示在这里。")}</small>
            </span>
          </div>
        ) : null
      ) : null}
    </section>
  );
}
