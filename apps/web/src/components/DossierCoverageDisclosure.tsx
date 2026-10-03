import type { ReactNode } from "react";

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
  return (
    <details className="advanced-filter-panel dossier-coverage-disclosure" open={available > 0 || undefined}>
      <summary>
        数据收录与缺失信息
        <span>
          {available} / {total} 个信息领域有记录
        </span>
      </summary>
      {children}
    </details>
  );
}
