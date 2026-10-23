import { formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { CompetitiveProgram } from "../../../lib/contracts/target";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
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
  const text = useMessages(targetPipelineMessages);
  return (
    <ScrollableTableRegion ariaLabel={text("靶点研发药物概览")}>
      <table aria-label={text("靶点研发药物概览")}>
        <thead>
          <tr>
            <th scope="col">{text("对比")}</th>
            <th scope="col">{text("药物")}</th>
            {visibleColumns.has("organizations") ? <th scope="col">{text("研发机构")}</th> : null}
            {visibleColumns.has("targets") ? <th scope="col">{text("靶点组合")}</th> : null}
            {visibleColumns.has("mechanism") ? <th scope="col">{text("类型 / 机制")}</th> : null}
            {visibleColumns.has("indications") ? <th scope="col">{text("适应症与阶段")}</th> : null}
            {visibleColumns.has("global_phase") ? <th scope="col">{text("全球最高阶段")}</th> : null}
            {visibleColumns.has("china_phase") ? <th scope="col">{text("中国最高阶段")}</th> : null}
            {visibleColumns.has("status") ? <th scope="col">{text("项目状态")}</th> : null}
            {visibleColumns.has("clinical") ? <th scope="col">{text("临床结果")}</th> : null}
            {visibleColumns.has("innovation") ? <th scope="col">{text("创新类型")}</th> : null}
            {visibleColumns.has("updated") ? <th scope="col">{text("最近更新")}</th> : null}
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
                    aria-label={text("选择对比 {name}", { name: item.drug_name })}
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
                  <small> · {text("{count} 个研发项目", { count: item.project_count ?? indications.length })}</small>
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
                      <small>
                        {text(" · 机制：")}
                        {(item.mechanisms_of_action ?? []).join("；")}
                      </small>
                    ) : null}
                  </td>
                ) : null}
                {visibleColumns.has("indications") ? (
                  <td>
                    {indications.length ? (
                      <ul
                        className="program-history indication-preview"
                        aria-label={text("{name} 适应症与阶段", { name: item.drug_name })}
                      >
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
                              text("适应症未披露")
                            )}{" "}
                            <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                          </li>
                        ))}
                        {indications.length > 2 ? (
                          <details className="program-history">
                            <summary>
                              {text("查看其余 {count} 个适应症项目", { count: indications.length - 2 })}
                            </summary>
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
                                    text("适应症未披露")
                                  )}{" "}
                                  <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                                </li>
                              ))}
                            </ol>
                          </details>
                        ) : null}
                      </ul>
                    ) : (
                      <span>{text("适应症未披露")}</span>
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
                      {text("· 在研 {active} · 已停止 {inactive} · 未披露 {unknown}", {
                        active: statuses.active ?? 0,
                        inactive: statuses.inactive ?? 0,
                        unknown: statuses.unknown ?? 0,
                      })}
                    </small>
                  </td>
                ) : null}
                {visibleColumns.has("clinical") ? (
                  <td>
                    {item.has_clinical_results ? text("已有结果") : text("暂无结果")}
                    <small>{text(" · {count} 项临床试验", { count: item.clinical_trial_count ?? 0 })}</small>
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
