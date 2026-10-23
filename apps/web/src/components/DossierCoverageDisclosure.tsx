import type { ReactNode } from "react";
import { useLocale } from "../lib/i18n";
import { dossierRecordText as t } from "../lib/i18n/dossierRecords";

/** Missing domain coverage stays inspectable without filling the overview with repeated zero rows. */
export function DossierCoverageDisclosure({
  available,
  total,
  children,
}: {
  available: number;
  total: number;
  children: ReactNode;
}) {
  useLocale();
  return (
    <details className="advanced-filter-panel dossier-coverage-disclosure" open={available > 0 || undefined}>
      <summary>
        {t("数据收录与缺失信息")}
        <span>{t("{available} / {total} 个信息领域有记录", { available, total })}</span>
      </summary>
      {children}
    </details>
  );
}
