import { Building2, CalendarDays, Newspaper } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState, formatDate, StatusBadge, stringifyParty } from "../../components/common";
import { PatentTimeline } from "../../components/PatentTimeline";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { ClinicalTrial, Deal, PatentFamily, RegulatoryEvent, TargetNewsEvent } from "../../lib/contracts/target";
import { clinicalTrialPhaseLabel, clinicalTrialStatusLabel } from "../../lib/trialDisplay";

export function Trials({
  items,
  onOpen,
  onOpenTrial,
}: {
  items: ClinicalTrial[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  const pageSize = 10;
  const [visibleCount, setVisibleCount] = useState(Math.min(pageSize, items.length));
  useEffect(() => {
    setVisibleCount(Math.min(pageSize, items.length));
  }, [items]);
  if (!items.length) return <EmptyState title="暂无关联临床试验" />;
  const visibleItems = items.slice(0, visibleCount);
  const remainingCount = items.length - visibleItems.length;
  return (
    <div>
      <p className="result-summary" role="status" aria-live="polite">
        当前显示 {visibleItems.length} / 共 {items.length} 项临床试验
      </p>
      <div className="record-list">
        {visibleItems.map((item) => (
          <TrialRecord key={item.id} item={item} onOpen={onOpen} onOpenTrial={onOpenTrial} />
        ))}
      </div>
      {items.length > pageSize ? (
        <nav className="sar-pagination" aria-label="靶点临床试验分段浏览">
          {remainingCount ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => setVisibleCount((count) => Math.min(count + pageSize, items.length))}
            >
              继续显示 {Math.min(pageSize, remainingCount)} 项
            </button>
          ) : (
            <button className="secondary-button" type="button" onClick={() => setVisibleCount(pageSize)}>
              收起至前 {pageSize} 项
            </button>
          )}
        </nav>
      ) : null}
    </div>
  );
}

function TrialRecord({
  item,
  onOpen,
  onOpenTrial,
}: {
  item: ClinicalTrial;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  const [showAllConditions, setShowAllConditions] = useState(false);
  const collapsibleConditions = item.conditions.length > 3;
  const visibleConditions = showAllConditions ? item.conditions : item.conditions.slice(0, 3);

  return (
    <article>
      <div className="record-icon">
        <CalendarDays size={18} />
      </div>
      <div>
        <span className="record-kicker">
          {item.registry_id} · {item.phases.map(clinicalTrialPhaseLabel).join(" / ") || "阶段未记录"}
        </span>
        <h3>
          <button className="table-link-button" type="button" onClick={() => onOpenTrial(item.id)}>
            {item.official_title}
          </button>
        </h3>
        <p>{visibleConditions.join("、") || "适应症未记录"}</p>
        {collapsibleConditions ? (
          <button
            className="text-button"
            type="button"
            aria-expanded={showAllConditions}
            onClick={() => setShowAllConditions((value) => !value)}
          >
            {showAllConditions ? "收起适应症" : `查看全部 ${item.conditions.length} 项适应症`}
          </button>
        ) : null}
        <div className="record-meta">
          <span>入组 {item.enrollment ?? "--"}</span>
          <span>{item.sponsors.map(stringifyParty).join("、") || "申办方未记录"}</span>
          <span>
            {formatDate(item.start_date)} - {formatDate(item.completion_date)}
          </span>
        </div>
      </div>
      <StatusBadge value={item.overall_status ?? "UNKNOWN"} label={clinicalTrialStatusLabel(item.overall_status)} />
      <ProvenanceButton
        selection={{ resourceType: "clinical_trial", resourceId: item.id, label: item.registry_id }}
        onOpen={onOpen}
      />
    </article>
  );
}

export function Patents({
  items,
  onOpen,
  onOpenPatent,
}: {
  items: PatentFamily[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenPatent: (patentId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联专利族" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点关联专利族">
      <table aria-label="靶点关联专利族">
        <thead>
          <tr>
            <th>专利族</th>
            <th>标题</th>
            <th>申请人</th>
            <th>优先权日</th>
            <th>法律状态</th>
            <th>预计到期</th>
            <th>事件与权利要求</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="mono-cell">{item.family_identifier}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenPatent(item.id)}
                  aria-label={`打开专利族详情：${item.family_identifier}`}
                >
                  {item.title}
                </button>
              </td>
              <td>{item.applicants.join("、") || "--"}</td>
              <td>{formatDate(item.priority_date)}</td>
              <td>
                <StatusBadge value={item.legal_status ?? "unknown"} />
              </td>
              <td>{formatDate(item.expiration_date)}</td>
              <td>
                <PatentTimeline patent={item} />
              </td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "patent_family", resourceId: item.id, label: item.family_identifier }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

export function Deals({
  items,
  onOpen,
  onOpenDeal,
}: {
  items: Deal[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联交易" />;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div className="record-icon">
            <Building2 size={18} />
          </div>
          <div>
            <span className="record-kicker">
              {item.deal_type} · {formatDate(item.announced_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenDeal(item.id)}
                aria-label={`打开交易详情：${item.parties.map(stringifyParty).join(" × ") || "交易方未记录"}`}
              >
                {item.parties.map(stringifyParty).join(" × ") || "交易方未记录"}
              </button>
            </h3>
            <p>{item.territory ?? "地域条款未记录"}</p>
            <div className="record-meta">
              <span>首付款 {money(item.upfront_amount, item.currency)}</span>
              <span>潜在总额 {money(item.total_potential_amount, item.currency)}</span>
            </div>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "deal", resourceId: item.id, label: `${item.deal_type} 交易` }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}

export function RegulatoryEvents({
  items,
  onOpen,
  onOpenRegulatoryEvent,
}: {
  items: RegulatoryEvent[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenRegulatoryEvent: (eventId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联监管事件" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点关联监管事件">
      <table aria-label="靶点关联监管事件">
        <thead>
          <tr>
            <th>监管机构</th>
            <th>事件</th>
            <th>标题</th>
            <th>申请号</th>
            <th>状态</th>
            <th>决定日期</th>
            <th>来源</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.agency}</strong>
                <small className="table-secondary">{item.jurisdiction}</small>
              </td>
              <td>{item.event_type.replaceAll("_", " ")}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenRegulatoryEvent(item.id)}
                  aria-label={`打开监管事件详情：${item.title}`}
                >
                  {item.title}
                </button>
              </td>
              <td className="mono-cell">{item.application_number ?? item.event_identifier}</td>
              <td>
                <StatusBadge value={item.status ?? item.event_type} />
              </td>
              <td>{formatDate(item.decision_date)}</td>
              <td className="mono-cell">{item.source_document_id ?? "--"}</td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "regulatory_event", resourceId: item.id, label: item.title }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

export function NewsEvents({
  items,
  onOpen,
  onOpenNewsEvent,
}: {
  items: TargetNewsEvent[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenNewsEvent: (eventId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联新闻或会议动态" />;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div className="record-icon">
            <Newspaper size={18} />
          </div>
          <div>
            <span className="record-kicker">
              {item.event_type} · {formatDate(item.published_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenNewsEvent(item.id)}
                aria-label={`打开新闻事件详情：${item.title}`}
              >
                {item.title}
              </button>
            </h3>
            <p>{item.summary ?? item.venue ?? item.event_identifier}</p>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "news_event", resourceId: item.id, label: item.title }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
function money(value: number | null, currency: string | null): string {
  if (value === null) return "--";
  return `${currency ?? ""} ${new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 2 }).format(value)}`.trim();
}
