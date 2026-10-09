import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import type { CollectionEntity } from "../lib/contracts/collections";
import { formattingLocale, useMessages } from "../lib/i18n";
import { collectionMatrixMessages } from "../lib/i18n/collectionMatrix";
import { localizedProgramModality } from "../lib/i18n/programVocabulary";
import {
  type DrugComparisonProfile,
  externalIdentifiers,
  missingValue,
  profilePhase,
  profileStatusSummary,
  summarizedValues,
} from "./collectionComparisonPresentation";
import { formatDate } from "./common";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

function DrugProfileRow({
  label,
  profiles,
  render,
}: {
  label: string;
  profiles: DrugComparisonProfile[];
  render: (profile: DrugComparisonProfile) => ReactNode;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {profiles.map((profile) => (
        <td key={profile.entity.id}>{render(profile)}</td>
      ))}
    </tr>
  );
}

export function DrugComparisonMatrix({
  profiles,
  onOpenEntity,
}: {
  profiles: DrugComparisonProfile[];
  onOpenEntity: (entity: CollectionEntity) => void;
}) {
  const text = useMessages(collectionMatrixMessages);
  return (
    <ScrollableTableRegion ariaLabel={text("研发情报对比表")} className="entity-comparison-region">
      <table
        className="entity-comparison-table"
        aria-label={text("研发情报对比表")}
        style={{ minWidth: `${170 + profiles.length * 240}px` }}
      >
        <thead>
          <tr>
            <th scope="col">{text("比较维度")}</th>
            {profiles.map((profile) => (
              <th scope="col" key={profile.entity.id}>
                <button
                  type="button"
                  className="comparison-entity-link"
                  aria-label={text("打开 {name} 详情", { name: profile.entity.name })}
                  onClick={() => onOpenEntity(profile.entity)}
                >
                  <span>
                    <strong>{profile.entity.name}</strong>
                    <small>{text("药物")}</small>
                  </span>
                  <ExternalLink size={15} aria-hidden="true" />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>{text("基础信息")}</th>
          </tr>
          <DrugProfileRow label={text("类型")} profiles={profiles} render={() => text("药物")} />
          <DrugProfileRow
            label={text("说明")}
            profiles={profiles}
            render={(profile) => profile.entity.description || missingValue()}
          />
          <DrugProfileRow
            label={text("资料编号")}
            profiles={profiles}
            render={(profile) => externalIdentifiers(profile.entity)}
          />
          <DrugProfileRow
            label={text("查询时间")}
            profiles={profiles}
            render={(profile) => formatDate(profile.as_of, true)}
          />
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>{text("研发格局")}</th>
          </tr>
          <DrugProfileRow
            label={text("作用靶点")}
            profiles={profiles}
            render={(profile) => summarizedValues(profile.target_names)}
          />
          <DrugProfileRow
            label={text("适应症")}
            profiles={profiles}
            render={(profile) => summarizedValues(profile.indication_names)}
          />
          <DrugProfileRow
            label={text("最高阶段")}
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_phase)}
          />
          <DrugProfileRow
            label={text("全球最高阶段")}
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_global_phase)}
          />
          <DrugProfileRow
            label={text("中国最高阶段")}
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_china_phase)}
          />
          <DrugProfileRow
            label={text("研发机构")}
            profiles={profiles}
            render={(profile) => summarizedValues(profile.organization_names)}
          />
          <DrugProfileRow
            label={text("药物类型")}
            profiles={profiles}
            render={(profile) => summarizedValues(profile.summary.modalities.map(localizedProgramModality))}
          />
          <DrugProfileRow label={text("项目状态")} profiles={profiles} render={profileStatusSummary} />
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>{text("研发覆盖")}</th>
          </tr>
          <DrugProfileRow
            label={text("研发项目")}
            profiles={profiles}
            render={(profile) => profile.summary.program_count.toLocaleString(formattingLocale())}
          />
          <DrugProfileRow
            label={text("作用靶点数")}
            profiles={profiles}
            render={(profile) => profile.summary.target_count.toLocaleString(formattingLocale())}
          />
          <DrugProfileRow
            label={text("适应症数")}
            profiles={profiles}
            render={(profile) => profile.summary.indication_count.toLocaleString(formattingLocale())}
          />
          <DrugProfileRow
            label={text("研发机构数")}
            profiles={profiles}
            render={(profile) => profile.summary.organization_count.toLocaleString(formattingLocale())}
          />
          <DrugProfileRow
            label={text("最近进展")}
            profiles={profiles}
            render={(profile) =>
              profile.summary.latest_status_date ? formatDate(profile.summary.latest_status_date) : missingValue()
            }
          />
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
