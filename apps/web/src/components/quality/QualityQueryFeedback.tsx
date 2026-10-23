import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { ErrorState, Spinner } from "../common";
export function QualityQueryFeedback({
  query,
  label,
  cached = false,
}: {
  query: { isPending: boolean; error: unknown; refetch: () => unknown };
  label: string;
  cached?: boolean;
}) {
  return (
    <>
      {query.isPending ? <Spinner label={label} /> : null}
      {query.error ? (
        <>
          {cached ? (
            <p role="status" className="field-help">
              {t("读取失败；下方仅显示上次成功读取的记录，恢复前不能提交处置。")}
            </p>
          ) : null}
          <ErrorState
            message={query.error instanceof Error ? query.error.message : t("读取失败")}
            retry={() => void query.refetch()}
          />
        </>
      ) : null}
    </>
  );
}
