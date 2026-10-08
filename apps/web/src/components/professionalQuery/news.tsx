import { RefreshCw } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import { newsEntityTypes } from "../../lib/newsDisplay";
import { EntityFilterSelect } from "../EntityFilterSelect";
import { DateRange, GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "newsCatalog"
  | "newsCatalogState"
  | "newsEventTypeOptions"
  | "newsPublisherOptions"
  | "newsLanguageOptions"
  | "newsVenueOptions"
  | "draft"
  | "update"
  | "updateDateRange"
>;

export function NewsFields({
  newsCatalog,
  newsCatalogState,
  newsEventTypeOptions,
  newsPublisherOptions,
  newsLanguageOptions,
  newsVenueOptions,
  draft,
  update,
  updateDateRange,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      <EntityFilterSelect
        label={t("关联实体")}
        entityType={newsEntityTypes}
        value={draft.newsEntityId}
        onChange={(value) => update("newsEntityId", value)}
        placeholder={t("输入药品、靶点、疾病、机构或技术")}
      />
      {newsCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          {t("正在读取新闻与会议筛选选项")}
        </div>
      ) : null}
      {newsCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>{t("新闻与会议筛选选项暂不可用")}</span>
          <button type="button" className="text-button" onClick={() => void newsCatalog.refetch()}>
            <RefreshCw size={13} />
            {t("重试")}
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label={t("事件类型")}
        options={newsEventTypeOptions}
        value={draft.newsEventType}
        state={newsCatalogState}
        onChange={(value) => update("newsEventType", value)}
      />
      <GovernedFacetSelect
        label={t("发布方")}
        options={newsPublisherOptions}
        value={draft.newsPublisher}
        state={newsCatalogState}
        onChange={(value) => update("newsPublisher", value)}
      />
      <GovernedFacetSelect
        label={t("语言")}
        options={newsLanguageOptions}
        value={draft.newsLanguage}
        state={newsCatalogState}
        onChange={(value) => update("newsLanguage", value)}
      />
      <GovernedFacetSelect
        label={t("会议 / 场景")}
        options={newsVenueOptions}
        value={draft.newsVenue}
        state={newsCatalogState}
        onChange={(value) => update("newsVenue", value)}
      />
      <label>
        <span>{t("内容范围")}</span>
        <select
          value={draft.newsContentScope}
          aria-label={t("内容范围")}
          onChange={(event) => update("newsContentScope", event.target.value as "" | "research")}
        >
          <option value="">{t("全部资讯")}</option>
          <option value="research">{t("论文与会议")}</option>
        </select>
      </label>
      <DateRange
        label={t("发布日期")}
        from={draft.newsPublishedFrom}
        to={draft.newsPublishedTo}
        onChange={(from, to) => updateDateRange("newsPublishedFrom", "newsPublishedTo", from, to)}
      />
    </>
  );
}
