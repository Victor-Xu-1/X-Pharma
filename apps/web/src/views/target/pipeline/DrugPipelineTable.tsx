import { formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { CompetitiveProgram } from "../../../lib/contracts/target";
import { programModalityLabel } from "../../../lib/programDisplay";
import type { TargetEntityOpener } from "../types";
import {
  developmentPhaseLabel,
  organizationRoleLabel,
  pipelineProgramStatusLabel,
  type TargetDrugColumnKey,
} from "./presentation";

export function DrugPipeline({
  items,
  onOpenEntity,
  selectedDrugIds,
  onToggleDrug,
  visibleColumns,
}: {
  items: CompetitiveProgram[];
  onOpenEntity: TargetEntityOpener;
  selectedDrugIds: Set<string>;
  onToggleDrug: (drugId: string, selected: boolean) => void;
  visibleColumns: Set<TargetDrugColumnKey>;
}) {
  return (
    <ScrollableTableRegion ariaLabel="靶点研发药物概览">
      <table aria-label="靶点研发药物概览">
        <thead>
          <tr>
            <th scope="col">对比</th>
            <th scope="col">药物</th>
            {visibleColumns.has("organizations") ? <th scope="col">研发机构</th> : null}
            {visibleColumns.has("targets") ? <th scope="col">靶点组合</th> : null}
            {visibleColumns.has("mechanism") ? <th scope="col">类型 / 机制</th> : null}
            {visibleColumns.has("indications") ? <th scope="col">适应症与阶段</th> : null}
            {visibleColumns.has("global_phase") ? <th scope="col">全球最高阶段</th> : null}
            {visibleColumns.has("china_phase") ? <th scope="col">中国最高阶段</th> : null}
            {visibleColumns.has("status") ? <th scope="col">项目状态</th> : null}
            {visibleColumns.has("clinical") ? <th scope="col">临床结果</th> : null}
            {visibleColumns.has("innovation") ? <th scope="col">创新类型</th> : null}
            {visibleColumns.has("updated") ? <th scope="col">最近更新</th> : null}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const organizations = item.organizations ?? [];
            const targets = item.targets ?? [];
            const indications = item.indications ?? [];
            const statuses = item.program_status_counts ?? {};
            return (
              <tr key={item.drug_entity_id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择对比 ${item.drug_name}`}
                    checked={selectedDrugIds.has(item.drug_entity_id)}
                    onChange={(event) => onToggleDrug(item.drug_entity_id, event.target.checked)}
                  />
                </td>
                <td>
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("drug", item.drug_entity_id)}
                  >
                    {item.drug_name}
                  </button>
                  <small> · {item.project_count ?? indications.length} 个研发项目</small>
                </td>
                {visibleColumns.has("organizations") ? (
                  <td>
                    {organizations.length
                      ? organizations.map((organization, index) => (
                          <span key={organization.entity_id}>
                            {index ? "、" : ""}
                            <button
                              className="table-link-button"
                              type="button"
                              onClick={() => onOpenEntity("organization", organization.entity_id)}
                            >
                              {organization.name}
                            </button>
                            <small>{organization.role ? `（${organizationRoleLabel(organization.role)}）` : ""}</small>
                          </span>
                        ))
                      : (item.organization_name ?? "--")}
                  </td>
                ) : null}
                {visibleColumns.has("targets") ? (
                  <td>
                    {targets.length
                      ? targets.map((target, index) => (
                          <span key={target.entity_id}>
                            {index ? " + " : ""}
                            <button
                              className="table-link-button"
                              type="button"
                              onClick={() => onOpenEntity("target", target.entity_id)}
                            >
                              {target.name}
                            </button>
                          </span>
                        ))
                      : (item.target_name ?? "--")}
                  </td>
                ) : null}
                {visibleColumns.has("mechanism") ? (
                  <td>
                    {(item.modalities ?? []).map(programModalityLabel).join("、") || "--"}
                    {(item.mechanisms_of_action ?? []).length ? (
                      <small> · 机制：{(item.mechanisms_of_action ?? []).join("；")}</small>
                    ) : null}
                  </td>
                ) : null}
                {visibleColumns.has("indications") ? (
                  <td>
                    {indications.length ? (
                      <ul className="program-history indication-preview" aria-label={`${item.drug_name} 适应症与阶段`}>
                        {indications.slice(0, 2).map((indication) => (
                          <li key={indication.program_id}>
                            {indication.disease_entity_id && indication.disease_name ? (
                              <button
                                className="table-link-button"
                                type="button"
                                onClick={() => onOpenEntity("disease", indication.disease_entity_id as string)}
                              >
                                {indication.disease_name}
                              </button>
                            ) : (
                              "适应症未披露"
                            )}{" "}
                            <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                          </li>
                        ))}
                        {indications.length > 2 ? (
                          <details className="program-history">
                            <summary>查看其余 {indications.length - 2} 个适应症项目</summary>
                            <ol>
                              {indications.slice(2).map((indication) => (
                                <li key={indication.program_id}>
                                  {indication.disease_entity_id && indication.disease_name ? (
                                    <button
                                      className="table-link-button"
                                      type="button"
                                      onClick={() => onOpenEntity("disease", indication.disease_entity_id as string)}
                                    >
                                      {indication.disease_name}
                                    </button>
                                  ) : (
                                    "适应症未披露"
                                  )}{" "}
                                  <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                                </li>
                              ))}
                            </ol>
                          </details>
                        ) : null}
                      </ul>
                    ) : (
                      <span>适应症未披露</span>
                    )}
                  </td>
                ) : null}
                {visibleColumns.has("global_phase") ? (
                  <td>
                    <StatusBadge value={developmentPhaseLabel(item.global_phase ?? item.phase)} />
                    {item.global_phase_started_at ? <small> · {formatDate(item.global_phase_started_at)}</small> : null}
                  </td>
                ) : null}
                {visibleColumns.has("china_phase") ? (
                  <td>
                    {item.china_phase ? <StatusBadge value={developmentPhaseLabel(item.china_phase)} /> : "--"}
                    {item.china_phase_started_at ? <small> · {formatDate(item.china_phase_started_at)}</small> : null}
                  </td>
                ) : null}
                {visibleColumns.has("status") ? (
                  <td>
                    <span className="status-badge">{pipelineProgramStatusLabel(item)}</span>
                    <small>
                      {" "}
                      · 在研 {statuses.active ?? 0} · 已停止 {statuses.inactive ?? 0} · 未披露 {statuses.unknown ?? 0}
                    </small>
                  </td>
                ) : null}
                {visibleColumns.has("clinical") ? (
                  <td>
                    {item.has_clinical_results ? "已有结果" : "暂无结果"}
                    <small> · {item.clinical_trial_count ?? 0} 项临床试验</small>
                  </td>
                ) : null}
                {visibleColumns.has("innovation") ? <td>{(item.innovation_types ?? []).join("、") || "--"}</td> : null}
                {visibleColumns.has("updated") ? <td>{formatDate(item.status_date)}</td> : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
