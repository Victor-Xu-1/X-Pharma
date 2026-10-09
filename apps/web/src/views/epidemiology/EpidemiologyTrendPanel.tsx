import { X } from "lucide-react";
import { lazy, Suspense } from "react";
import { EmptyState, ErrorState, Spinner } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EpidemiologyTrendResult } from "../../lib/contracts/epidemiology";
import { useLocale } from "../../lib/i18n";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
import { publicCoverageNotice } from "../../lib/publicWarnings";
import { formatNumber, measureValue, periodLabel, type TrendSelection } from "./presentation";

const TrendLineChart = lazy(() =>
  import("../../components/TrendLineChart").then((module) => ({ default: module.TrendLineChart })),
);
export function EpidemiologyTrendPanel({
  selection,
  data,
  error,
  loading,
  onClose,
  onRetry,
}: {
  selection: TrendSelection;
  data: EpidemiologyTrendResult | undefined;
  error: unknown;
  loading: boolean;
  onClose: () => void;
  onRetry: () => void;
}) {
  useLocale();
  return (
    <section
      className="epidemiology-trend-panel"
      aria-label={t("{disease} 同口径趋势", { disease: selection.diseaseName })}
    >
      <header>
        <div>
          <span>{t("同口径观测趋势")}</span>
          <h3>
            {selection.diseaseName} · {measureValue(selection.filters.measure)}
          </h3>
          <p>
            {selection.filters.geography} · {selection.filters.populationScope} · {selection.filters.unit}
          </p>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label={t("关闭趋势")}
          title={t("关闭趋势")}
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </header>
      {loading ? <Spinner label={t("正在读取同口径趋势")} /> : null}
      {error ? (
        <ErrorState message={error instanceof Error ? error.message : t("趋势加载失败")} retry={onRetry} />
      ) : null}
      {error && data ? <p role="status">{t("显示上次可读取的同口径观测")}</p> : null}
      {data?.items.length ? (
        <div className="trend-table-wrap">
          <Suspense fallback={<Spinner label={t("正在加载趋势图")} />}>
            <TrendLineChart
              ariaLabel={t("{disease} {measure} 趋势图", {
                disease: selection.diseaseName,
                measure: measureValue(selection.filters.measure),
              })}
              valueLabel={selection.filters.unit}
              points={data.items.map((item) => ({
                label: periodLabel(item),
                axisLabel: periodLabel(item).replace(" - ", "\n– "),
                value: item.value,
                lowerBound: item.lower_bound,
                upperBound: item.upper_bound,
              }))}
            />
          </Suspense>
          <ScrollableTableRegion ariaLabel={t("同口径趋势表滚动区域")}>
            <table aria-label={t("同口径趋势数据")}>
              <thead>
                <tr>
                  <th>{t("观察期")}</th>
                  <th>{t("估计值")}</th>
                  <th>{t("区间")}</th>
                  <th>{t("样本量")}</th>
                  <th>{t("发布机构")}</th>
                  <th>{t("方法学")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{periodLabel(item)}</td>
                    <td>
                      <strong>{formatNumber(item.value)}</strong> {item.unit}
                    </td>
                    <td>
                      {formatNumber(item.lower_bound)} - {formatNumber(item.upper_bound)}
                    </td>
                    <td>{formatNumber(item.sample_size)}</td>
                    <td>{item.publisher_entity?.name ?? "--"}</td>
                    <td>{item.methodology ?? t("未标注")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          <footer>
            {data.truncated ? (
              <p role="status">
                {t("仅显示返回的 {count} 项同口径观测，完整趋势可能有更多记录。", { count: data.items.length })}
              </p>
            ) : null}
            {publicCoverageNotice(data.warnings)}
          </footer>
        </div>
      ) : data ? (
        <EmptyState title={t("暂无可比较趋势")} detail={t("需要相同指标、单位、地区和人群口径的多期观测。")} />
      ) : null}
    </section>
  );
}
