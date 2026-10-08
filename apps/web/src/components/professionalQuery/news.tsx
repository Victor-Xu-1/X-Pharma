import { RefreshCw } from "lucide-react";
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
  return (
    <>
      <EntityFilterSelect
        label="关联实体"
        entityType={newsEntityTypes}
        value={draft.newsEntityId}
        onChange={(value) => update("newsEntityId", value)}
        placeholder="输入药品、靶点、疾病、机构或技术"
      />
      {newsCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          正在读取新闻与会议筛选选项
        </div>
      ) : null}
      {newsCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>新闻与会议筛选选项暂不可用</span>
          <button type="button" className="text-button" onClick={() => void newsCatalog.refetch()}>
            <RefreshCw size={13} />
            重试
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label="事件类型"
        options={newsEventTypeOptions}
        value={draft.newsEventType}
        state={newsCatalogState}
        onChange={(value) => update("newsEventType", value)}
      />
      <GovernedFacetSelect
        label="发布方"
        options={newsPublisherOptions}
        value={draft.newsPublisher}
        state={newsCatalogState}
        onChange={(value) => update("newsPublisher", value)}
      />
      <GovernedFacetSelect
        label="语言"
        options={newsLanguageOptions}
        value={draft.newsLanguage}
        state={newsCatalogState}
        onChange={(value) => update("newsLanguage", value)}
      />
      <GovernedFacetSelect
        label="会议 / 场景"
        options={newsVenueOptions}
        value={draft.newsVenue}
        state={newsCatalogState}
        onChange={(value) => update("newsVenue", value)}
      />
      <label>
        <span>内容范围</span>
        <select
          value={draft.newsContentScope}
          onChange={(event) => update("newsContentScope", event.target.value as "" | "research")}
        >
          <option value="">全部资讯</option>
          <option value="research">论文与会议</option>
        </select>
      </label>
      <DateRange
        label="发布日期"
        from={draft.newsPublishedFrom}
        to={draft.newsPublishedTo}
        onChange={(from, to) => updateDateRange("newsPublishedFrom", "newsPublishedTo", from, to)}
      />
    </>
  );
}
