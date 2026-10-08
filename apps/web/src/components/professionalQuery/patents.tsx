import { RefreshCw } from "lucide-react";
import type { PatentEntityType } from "../../lib/professionalSearch";
import { EntityFilterSelect } from "../EntityFilterSelect";
import { DateRange, GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "patentCatalog"
  | "patentCatalogState"
  | "patentLegalStatusOptions"
  | "draft"
  | "update"
  | "updateDateRange"
  | "updatePatentEntityType"
>;

export function PatentsFields({
  patentCatalog,
  patentCatalogState,
  patentLegalStatusOptions,
  draft,
  update,
  updateDateRange,
  updatePatentEntityType,
}: Props) {
  return (
    <>
      <div className="professional-entity-row single">
        <label>
          <span>关联实体类型</span>
          <select
            value={draft.patentEntityType}
            onChange={(event) => updatePatentEntityType(event.target.value as PatentEntityType)}
          >
            <option value="target">靶点</option>
            <option value="drug">药品</option>
            <option value="disease">疾病/适应症</option>
            <option value="organization">机构</option>
          </select>
        </label>
        <EntityFilterSelect
          label="关联实体"
          entityType={draft.patentEntityType}
          value={draft.patentEntityId}
          onChange={(value) => update("patentEntityId", value)}
          placeholder="输入药品、靶点、适应症或机构"
        />
      </div>
      <label>
        <span>申请人</span>
        <input value={draft.applicant} onChange={(event) => update("applicant", event.target.value)} />
      </label>
      {patentCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          正在读取专利筛选选项
        </div>
      ) : null}
      {patentCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>专利筛选选项暂不可用</span>
          <button type="button" className="text-button" onClick={() => void patentCatalog.refetch()}>
            <RefreshCw size={13} />
            重试
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label="法律状态"
        options={patentLegalStatusOptions}
        value={draft.legalStatus}
        state={patentCatalogState}
        onChange={(value) => update("legalStatus", value)}
      />
      <DateRange
        label="优先权日期"
        from={draft.patentPriorityFrom}
        to={draft.patentPriorityTo}
        onChange={(from, to) => updateDateRange("patentPriorityFrom", "patentPriorityTo", from, to)}
      />
      <DateRange
        label="到期日期"
        from={draft.patentExpirationFrom}
        to={draft.patentExpirationTo}
        onChange={(from, to) => updateDateRange("patentExpirationFrom", "patentExpirationTo", from, to)}
      />
    </>
  );
}
