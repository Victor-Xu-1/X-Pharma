import { RefreshCw } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
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
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      <div className="professional-entity-row single">
        <label>
          <span>{t("关联实体类型")}</span>
          <select
            value={draft.patentEntityType}
            aria-label={t("关联实体类型")}
            onChange={(event) => updatePatentEntityType(event.target.value as PatentEntityType)}
          >
            <option value="target">{t("靶点")}</option>
            <option value="drug">{t("药品")}</option>
            <option value="disease">{t("疾病/适应症")}</option>
            <option value="organization">{t("机构")}</option>
          </select>
        </label>
        <EntityFilterSelect
          label={t("关联实体")}
          entityType={draft.patentEntityType}
          value={draft.patentEntityId}
          onChange={(value) => update("patentEntityId", value)}
          placeholder={t("输入药品、靶点、适应症或机构")}
        />
      </div>
      <label>
        <span>{t("申请人")}</span>
        <input value={draft.applicant} onChange={(event) => update("applicant", event.target.value)} />
      </label>
      {patentCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          {t("正在读取专利筛选选项")}
        </div>
      ) : null}
      {patentCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>{t("专利筛选选项暂不可用")}</span>
          <button type="button" className="text-button" onClick={() => void patentCatalog.refetch()}>
            <RefreshCw size={13} />
            {t("重试")}
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label={t("法律状态")}
        options={patentLegalStatusOptions}
        value={draft.legalStatus}
        state={patentCatalogState}
        onChange={(value) => update("legalStatus", value)}
      />
      <DateRange
        label={t("优先权日期")}
        from={draft.patentPriorityFrom}
        to={draft.patentPriorityTo}
        onChange={(from, to) => updateDateRange("patentPriorityFrom", "patentPriorityTo", from, to)}
      />
      <DateRange
        label={t("到期日期")}
        from={draft.patentExpirationFrom}
        to={draft.patentExpirationTo}
        onChange={(from, to) => updateDateRange("patentExpirationFrom", "patentExpirationTo", from, to)}
      />
    </>
  );
}
