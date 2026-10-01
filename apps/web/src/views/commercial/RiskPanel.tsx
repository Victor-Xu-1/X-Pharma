import { ChevronLeft, ChevronRight } from "lucide-react";
import { Spinner } from "../../components/common";
import type { CommercialRiskEvent, CommercialRiskFilter } from "../../lib/contracts/commercial";
import { RiskTable } from "./RiskTable";
import type { RiskAction } from "./types";

export function RiskPanel({
  items,
  totalItems,
  nextCursor,
  filter,
  isPending,
  canGoPrevious,
  busy,
  onFilter,
  onPrevious,
  onNext,
  onAction,
}: {
  items: CommercialRiskEvent[];
  totalItems: number;
  nextCursor: string | null;
  filter: CommercialRiskFilter;
  isPending: boolean;
  canGoPrevious: boolean;
  busy: string;
  onFilter: (value: CommercialRiskFilter) => void;
  onPrevious: () => void;
  onNext: (cursor: string) => void;
  onAction: (action: RiskAction) => void;
}) {
  return (
    <section className="risk-operations" aria-label="风险事件队列">
      <div className="risk-queue-toolbar">
        <label>
          <span>处置状态</span>
          <select
            aria-label="风险处置状态"
            value={filter}
            onChange={(event) => onFilter(event.target.value as CommercialRiskFilter)}
          >
            <option value="all">全部</option>
            <option value="open">未处置</option>
            <option value="acknowledged">已确认</option>
            <option value="resolved">已解决</option>
            <option value="dismissed">已排除</option>
          </select>
        </label>
        <span className="risk-queue-count" aria-live="polite">
          {isPending ? "正在读取" : `共 ${totalItems} 条`}
        </span>
        <div className="risk-queue-pagination">
          <button
            className="icon-button"
            type="button"
            title="上一页"
            aria-label="风险事件上一页"
            disabled={isPending || !canGoPrevious}
            onClick={onPrevious}
          >
            <ChevronLeft size={17} />
          </button>
          <button
            className="icon-button"
            type="button"
            title="下一页"
            aria-label="风险事件下一页"
            disabled={isPending || !nextCursor}
            onClick={() => {
              if (nextCursor) onNext(nextCursor);
            }}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
      {isPending ? <Spinner label="正在读取风险事件" /> : <RiskTable items={items} busy={busy} onAction={onAction} />}
    </section>
  );
}
