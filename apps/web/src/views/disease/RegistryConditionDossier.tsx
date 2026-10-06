import { ClipboardList } from "lucide-react";

import { formatDate } from "../../components/common";
import { EntityIdentityNotice } from "../../components/EntityIdentityNotice";
import { ResearchTabList, type ResearchTabOption } from "../../components/ResearchTabList";
import type { DiseaseDossier } from "../../lib/contracts/disease";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { DiseaseDossierSection } from "../../lib/workspaceRouting";
import { type DossierEntityOpener, Relationships, Trials } from "../EntityDossierView";

const tabs: Array<ResearchTabOption<DiseaseDossierSection>> = [
  { key: "overview", label: "登记条件概览" },
  { key: "trials", label: "关联试验" },
  { key: "relationships", label: "来源与关系" },
];

export function RegistryConditionDossier({
  data,
  activeSection,
  onSectionChange,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenTrial,
}: {
  data: DiseaseDossier;
  activeSection: DiseaseDossierSection;
  onSectionChange: (section: DiseaseDossierSection, replace?: boolean) => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenTrial: (trialId: string) => void;
}) {
  const section = tabs.some((tab) => tab.key === activeSection) ? activeSection : "overview";
  return (
    <section className="company-profile-page disease-profile-page">
      <header className="company-profile-header">
        <div className="company-profile-symbol">
          <ClipboardList size={23} />
        </div>
        <div className="company-profile-identity">
          <span>登记条件档案</span>
          <h2>{data.entity.name}</h2>
          <p>{String(data.entity.attributes.label_provider ?? "注册来源")}</p>
        </div>
      </header>
      <EntityIdentityNotice entity={data.entity} />
      <dl className="dossier-metrics">
        <div>
          <dt>关联登记试验</dt>
          <dd>{data.summary.clinical_trial_count}</dd>
        </div>
        <div>
          <dt>资料来源</dt>
          <dd>{data.coverage.find((item) => item.domain === "evidence")?.total ?? 0}</dd>
        </div>
        <div>
          <dt>查询时间</dt>
          <dd>{formatDate(data.as_of, true)}</dd>
        </div>
      </dl>
      <ResearchTabList
        tabs={tabs}
        activeTab={section}
        onChange={onSectionChange}
        ariaLabel="登记条件档案视图"
        idPrefix="condition-dossier"
      />
      <div
        className="dossier-body"
        role="tabpanel"
        id={`condition-dossier-panel-${section}`}
        aria-labelledby={`condition-dossier-tab-${section}`}
      >
        {section === "overview" ? (
          <p>以下记录使用此登记条件名称。登记标签不是已核实的标准疾病、确诊结论或药物获批用途。</p>
        ) : null}
        {section === "relationships" ? (
          <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={onOpenTypedEntity} />
        ) : (
          <Trials data={data} onOpen={onOpen} onOpenTrial={onOpenTrial} />
        )}
      </div>
    </section>
  );
}
