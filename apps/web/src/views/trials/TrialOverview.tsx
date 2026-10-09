import { EmptyState, formatDate } from "../../components/common";
import type { ClinicalTrialDetailRead } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";
import { clinicalCaption, clinicalText as t } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import {
  trialInitiationTypeLabels as initiationTypeLabels,
  trialResultEvaluationLabels as resultEvaluationLabels,
  trialTherapyLineLabels as therapyLineLabels,
} from "../../lib/trialFilters";
import { displayList, uniqueValues } from "./presentation";
import { DetailValue } from "./TrialDetailValue";
import { RoleEntityLinks } from "./TrialEntityLinks";
import { TrialRecordedDate } from "./TrialRecordedDate";
import type { TrialEntityOpener } from "./viewTypes";
import { trialRoleLabels } from "./vocabulary";

export function TrialOverview({
  data,
  onOpenEntity,
}: {
  data: ClinicalTrialDetailRead;
  onOpenEntity: TrialEntityOpener;
}) {
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>{t("关键属性")}</h3>
        <dl className="trial-detail-grid">
          <DetailValue term={t("注册号")} value={data.registry_id} />
          <DetailValue term={t("试验简称")} value={data.acronym} />
          <DetailValue
            term={t("发起类型")}
            value={
              initiationTypeLabels[data.initiation_type ?? ""]
                ? professionalEnumLabel(initiationTypeLabels[data.initiation_type ?? ""], data.initiation_type ?? "")
                : (data.initiation_type ?? t("未记录"))
            }
          />
          <DetailValue
            term={t("治疗线次")}
            value={displayList(
              data.therapy_lines.map((value) =>
                therapyLineLabels[value] ? professionalEnumLabel(therapyLineLabels[value], value) : value,
              ),
              t("未记录"),
              6,
            )}
          />
          <DetailValue term={t("研究类型")} value={localizedTrialStudyType(data.study_type)} />
          <DetailValue term={t("入组人数")} value={data.enrollment?.toLocaleString(formattingLocale())} />
          <DetailValue
            term={t("开始日期")}
            value={<TrialRecordedDate value={data.start_date} precision={data.start_date_precision} />}
          />
          <DetailValue
            term={t("完成日期")}
            value={<TrialRecordedDate value={data.completion_date} precision={data.completion_date_precision} />}
          />
          <DetailValue term={t("首次结果")} value={formatDate(data.results_first_posted)} />
          <DetailValue
            term={t("最优评价")}
            value={
              data.result_evaluation && resultEvaluationLabels[data.result_evaluation]
                ? professionalEnumLabel(resultEvaluationLabels[data.result_evaluation], data.result_evaluation)
                : (data.result_evaluation ?? t("未评价"))
            }
          />
        </dl>
      </section>
      <section>
        <h3>{t("适应症与干预")}</h3>
        <dl className="trial-detail-grid">
          <DetailValue term={t("适应症")} value={displayList(data.conditions, t("未记录"), 6)} />
          <DetailValue
            term={t("干预措施")}
            value={displayList(
              data.interventions.map((item) => item.name),
              t("未记录"),
              6,
            )}
          />
          <DetailValue
            term={t("申办方")}
            value={displayList(
              data.sponsors.map((item) => item.name),
              t("未记录"),
              6,
            )}
          />
          <DetailValue
            term={t("国家/地区")}
            value={displayList(uniqueValues(data.locations.map((item) => item.country)), t("未记录"), 8)}
          />
        </dl>
      </section>
      <section>
        <h3>{t("关联药物与靶点")}</h3>
        {(data.entity_roles ?? []).length ? (
          <div className="trial-role-groups">
            {Object.entries(trialRoleLabels).map(([role, label]) => {
              const roles = (data.entity_roles ?? []).filter((item) => item.role === role);
              if (!roles.length) return null;
              return (
                <div key={role}>
                  <span>{clinicalCaption(label)}</span>
                  <RoleEntityLinks roles={roles} acceptedRoles={[role]} onOpenEntity={onOpenEntity} />
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState title={t("暂无角色化药物或靶点关联")} />
        )}
      </section>
      <section>
        <h3>{t("关联实体")}</h3>
        {data.linked_entities.length ? (
          <div className="trial-linked-entities">
            {data.linked_entities.map((entity) => (
              <button
                className="secondary-button"
                type="button"
                key={entity.id}
                onClick={() => onOpenEntity(entity.entity_type, entity.id)}
              >
                {entity.name}
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title={t("暂无关联药物或靶点信息")} />
        )}
      </section>
    </div>
  );
}
