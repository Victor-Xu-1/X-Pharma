import type { DataSource } from "../../lib/contracts/dataFactory";
import type { ClinicalTrialsSort, PublicSourceDraft } from "./sourceRules";

export function SourceRoutingFields({
  sourceType,
  draft,
  onChange,
  onAbstractChange,
}: {
  sourceType: DataSource["source_type"];
  draft: PublicSourceDraft;
  onChange: (change: Partial<PublicSourceDraft>) => void;
  onAbstractChange: (include: boolean) => void;
}) {
  return (
    <>
      <label className="source-path-field">
        <span>
          {sourceType === "chembl"
            ? "ChEMBL 靶点编号"
            : sourceType === "pubmed"
              ? "PubMed 检索主题"
              : "ClinicalTrials.gov 检索主题"}
        </span>
        <input
          value={sourceType === "chembl" ? draft.targetChemblId : draft.queryTerm}
          onChange={(event) =>
            onChange(
              sourceType === "chembl" ? { targetChemblId: event.target.value } : { queryTerm: event.target.value },
            )
          }
          required
          maxLength={sourceType === "pubmed" ? 2000 : sourceType === "chembl" ? 32 : 1000}
          placeholder={sourceType === "chembl" ? "CHEMBL…" : "填写需要持续关注的检索条件"}
        />
      </label>
      <label>
        <span>单次最多抓取记录</span>
        <input
          type="number"
          min={1}
          max={sourceType === "chembl" && draft.includeActivities ? 25 : 1000}
          value={draft.maxRecords}
          onChange={(event) => onChange({ maxRecords: Number(event.target.value) })}
          required
        />
      </label>
      <label>
        <span>每页请求数量</span>
        <input
          type="number"
          min={1}
          max={sourceType === "pubmed" ? 200 : sourceType === "chembl" ? 100 : 1000}
          value={draft.pageSize}
          onChange={(event) => onChange({ pageSize: Number(event.target.value) })}
          required
        />
      </label>
      {sourceType !== "pubmed" ? (
        <>
          <label>
            <span>采集方式</span>
            <select
              value={draft.syncMode}
              onChange={(event) => onChange({ syncMode: event.target.value as PublicSourceDraft["syncMode"] })}
            >
              <option value="continuous">持续同步（分批续跑与复核）</option>
              <option value="snapshot">受限快照（只获取当前窗口）</option>
            </select>
          </label>
          {sourceType === "clinicaltrials_gov" && draft.syncMode === "continuous" ? (
            <>
              <label>
                <span>历史起始日期</span>
                <input
                  type="date"
                  value={draft.startDate}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(event) => onChange({ startDate: event.target.value })}
                  required
                />
              </label>
              <label>
                <span>日期分区（天）</span>
                <input
                  type="number"
                  min={1}
                  max={366}
                  value={draft.windowDays}
                  onChange={(event) => onChange({ windowDays: Number(event.target.value) })}
                  required
                />
              </label>
              <label>
                <span>更新回看（天）</span>
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={draft.overlapDays}
                  onChange={(event) => onChange({ overlapDays: Number(event.target.value) })}
                  required
                />
              </label>
              <label>
                <span>完整复核周期（天）</span>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={draft.reconcileIntervalDays}
                  onChange={(event) => onChange({ reconcileIntervalDays: Number(event.target.value) })}
                  required
                />
              </label>
            </>
          ) : null}
          <p className="field-help source-path-field">
            {draft.syncMode === "continuous"
              ? "记录上限只限制单批工作量，未完成的范围会自动续跑；不会把查询窗口外的历史数据删除。"
              : "只获取当前有限窗口，不表示全量历史已经同步。"}
          </p>
        </>
      ) : null}
      {sourceType === "pubmed" ? (
        <label className="source-checkbox-field">
          <input
            type="checkbox"
            checked={draft.includeAbstract}
            onChange={(event) => onAbstractChange(event.target.checked)}
          />
          <span>同时入库摘要</span>
        </label>
      ) : sourceType === "clinicaltrials_gov" ? (
        <label>
          <span>结果排序</span>
          <select
            value={draft.clinicalSort}
            onChange={(event) => onChange({ clinicalSort: event.target.value as ClinicalTrialsSort })}
          >
            <option value="LastUpdatePostDate:desc">最近更新优先</option>
            <option value="LastUpdatePostDate:asc">最早更新优先</option>
            <option value="StudyFirstPostDate:desc">最近首次发布优先</option>
            <option value="StudyFirstPostDate:asc">最早首次发布优先</option>
          </select>
        </label>
      ) : sourceType === "chembl" ? (
        <>
          <label className="source-checkbox-field">
            <input
              type="checkbox"
              checked={draft.includeActivities}
              onChange={(event) =>
                onChange({
                  includeActivities: event.target.checked,
                  ...(event.target.checked ? { maxRecords: Math.min(draft.maxRecords, 25) } : {}),
                })
              }
            />
            <span>补充该靶点的药物实验活性</span>
          </label>
          {draft.includeActivities ? (
            <label>
              <span>每个药物的活性样本上限</span>
              <input
                type="number"
                min={1}
                max={10}
                value={draft.activityLimit}
                onChange={(event) => onChange({ activityLimit: Number(event.target.value) })}
                required
              />
            </label>
          ) : null}
          <p className="field-help source-path-field">
            结构随药物元数据采集。活性保留单条实验值、关系符和来源，不合并重复实验；有界样本不代表完整活性覆盖。
          </p>
        </>
      ) : null}
    </>
  );
}
