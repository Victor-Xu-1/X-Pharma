import { EmptyState, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ClinicalTrialDetailRead } from "../../lib/generated";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { clinicalContentRows } from "./contentRows";
import { displayBoolean, displayList } from "./presentation";
import { DetailValue } from "./TrialDetailValue";

export function TrialDesign({ data }: { data: ClinicalTrialDetailRead }) {
  const design = data.study_design;
  const eligibility = data.eligibility;
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>{t("研究设计")}</h3>
        <dl className="trial-detail-grid">
          <DetailValue term={t("分配方式")} value={design.allocation} />
          <DetailValue term={t("干预模型")} value={design.intervention_model ?? design.observational_model} />
          <DetailValue term={t("主要目的")} value={design.primary_purpose} />
          <DetailValue term={t("时间视角")} value={design.time_perspective} />
          <DetailValue term={t("盲法")} value={design.masking} />
          <DetailValue term={t("盲法对象")} value={displayList(design.who_masked ?? [], t("未记录"), 8)} />
        </dl>
        {design.intervention_model_description ? (
          <div>
            <h4>{t("干预模型说明")}</h4>
            <p className="trial-detail-note">{design.intervention_model_description}</p>
          </div>
        ) : null}
        {design.masking_description ? (
          <div>
            <h4>{t("盲法说明")}</h4>
            <p className="trial-detail-note">{design.masking_description}</p>
          </div>
        ) : null}
      </section>
      <section>
        <h3>{t("队列与治疗组")}</h3>
        {data.arms.length ? (
          <div className="trial-arm-list">
            {clinicalContentRows(data.arms).map(({ value: arm, key }) => (
              <article key={key}>
                <div>
                  <strong>{arm.label}</strong>
                  <StatusBadge value={arm.type ?? t("未分类")} />
                </div>
                <p>{arm.description ?? t("未记录队列说明")}</p>
                <span>{displayList(arm.intervention_names ?? [], t("未关联干预"))}</span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title={t("暂无队列或治疗组记录")} />
        )}
      </section>
      <section>
        <h3>{t("入组资格")}</h3>
        <dl className="trial-detail-grid">
          <DetailValue term={t("最低年龄")} value={eligibility.minimum_age} />
          <DetailValue term={t("最高年龄")} value={eligibility.maximum_age} />
          <DetailValue term={t("性别")} value={eligibility.sex} />
          <DetailValue term={t("基于性别的资格")} value={displayBoolean(eligibility.gender_based)} />
          <DetailValue term={t("健康志愿者")} value={displayBoolean(eligibility.healthy_volunteers)} />
          <DetailValue term={t("抽样方式")} value={eligibility.sampling_method} />
        </dl>
        {eligibility.criteria ? (
          <ScrollableTableRegion className="trial-eligibility-criteria" ariaLabel={t("入组资格原文")}>
            <pre>{eligibility.criteria}</pre>
          </ScrollableTableRegion>
        ) : null}
      </section>
    </div>
  );
}
