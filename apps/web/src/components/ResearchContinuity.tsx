import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { useId, useState } from "react";
import { loadRecentResearch, researchActivityKeys } from "../lib/contracts/researchActivity";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";

export function ResearchContinuity({ onOpenEntity }: { onOpenEntity: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const regionId = useId();
  const recent = useQuery({
    queryKey: researchActivityKeys.recent,
    queryFn: ({ signal }) => loadRecentResearch(signal),
    enabled: open,
  });
  return (
    <section aria-label="研究连续性">
      <div className="research-entry">
        <button
          className="secondary-button"
          type="button"
          aria-expanded={open}
          aria-controls={regionId}
          onClick={() => setOpen((value) => !value)}
        >
          <History size={15} aria-hidden="true" />
          继续最近的研究
        </button>
        <p>查询药物、靶点、机构、疾病、临床、专利与交易；结果可查看来源和更新时间。</p>
      </div>
      <div id={regionId} hidden={!open}>
        {open ? (
          recent.isError ? (
            <ErrorState message={recent.error.message} retry={recent.refetch} />
          ) : recent.data === undefined ? (
            <Spinner label="正在读取最近研究" />
          ) : recent.data.length ? (
            <ul aria-label="最近研究档案">
              {recent.data.map(({ entity, visited_at }) => (
                <li key={entity.id}>
                  <button
                    className="table-link-button"
                    type="button"
                    aria-label={`继续研究 ${entity.name}`}
                    onClick={() => onOpenEntity(entity.id)}
                  >
                    {entity.name}
                  </button>
                  <span className="cell-subtitle">{formatDate(visited_at, true)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="暂无最近研究" detail="查看情报档案后，可以在这里继续。记录仅属于当前账号和组织。" />
          )
        ) : null}
      </div>
    </section>
  );
}
