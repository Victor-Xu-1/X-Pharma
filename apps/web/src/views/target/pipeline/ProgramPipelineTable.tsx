import { EmptyState, formatDate, StatusBadge } from "../../../components/common";
import { ProvenanceButton } from "../../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../../lib/contracts/provenance";
import type { CompetitiveProgram } from "../../../lib/contracts/target";
import type { TargetEntityOpener } from "../types";
import { developmentPhaseLabel, geographyLabel, programStatusLabel } from "./presentation";

export function Pipeline({
  items,
  onOpen,
  onOpenEntity,
  selectedDrugIds,
  onToggleDrug,
}: {
  items: CompetitiveProgram[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: TargetEntityOpener;
  selectedDrugIds?: Set<string>;
  onToggleDrug?: (drugId: string, selected: boolean) => void;
}) {
  if (!items.length) return <EmptyState title="暂无竞品管线记录" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点竞品研发管线">
      <table aria-label="靶点竞品研发管线">
        <thead>
          <tr>
            {onToggleDrug ? <th scope="col">对比</th> : null}
            <th>药物</th>
            <th>公司</th>
            <th>适应症</th>
            <th>机制/模态</th>
            <th>阶段</th>
            <th>状态日期</th>
            <th>阶段历史与里程碑</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              {onToggleDrug ? (
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择对比 ${item.drug_name}`}
                    checked={selectedDrugIds?.has(item.drug_entity_id) ?? false}
                    onChange={(event) => onToggleDrug(item.drug_entity_id, event.target.checked)}
                  />
                </td>
              ) : null}
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenEntity("drug", item.drug_entity_id)}
                >
                  {item.drug_name}
                </button>
              </td>
              <td>
                {item.organization_entity_id && item.organization_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("organization", item.organization_entity_id as string)}
                  >
                    {item.organization_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>
                {item.disease_entity_id && item.disease_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("disease", item.disease_entity_id as string)}
                  >
                    {item.disease_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>{item.mechanism_of_action ?? item.modality ?? "--"}</td>
              <td>
                <StatusBadge value={developmentPhaseLabel(item.phase)} />
              </td>
              <td>{formatDate(item.status_date)}</td>
              <td>
                <details className="program-history">
                  <summary>
                    {item.status_history?.length ?? 0} 个阶段 · {item.milestones?.length ?? 0} 个里程碑
                  </summary>
                  <ol>
                    {item.status_history?.map((event) => (
                      <li key={`${event.phase}-${event.effective_at}-${event.geography ?? "global"}`}>
                        <strong>{developmentPhaseLabel(event.phase)}</strong> · {formatDate(event.effective_at)}
                        {event.geography ? ` · ${geographyLabel(event.geography)}` : ""}
                        {event.status ? ` · ${programStatusLabel(event.status)}` : ""}
                      </li>
                    ))}
                    {item.milestones?.map((event) => (
                      <li key={`${event.milestone_type}-${event.occurred_at}-${event.title}`}>
                        <strong>{event.title}</strong> · {formatDate(event.occurred_at)}
                        {event.geography ? ` · ${geographyLabel(event.geography)}` : ""}
                      </li>
                    ))}
                  </ol>
                </details>
              </td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "development_program", resourceId: item.id, label: item.drug_name }}
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
