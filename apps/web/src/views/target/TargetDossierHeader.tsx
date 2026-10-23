import { ChevronDown, Dna } from "lucide-react";
import { formatDate } from "../../components/common";
import { EntityNames } from "../../components/EntityNames";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { TargetProfile } from "../../lib/contracts/target";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { targetDossierMessages } from "../../lib/i18n/targetDossier";
import { organismLabel, targetClassLabel, targetDisplayIdentity } from "../../lib/targetDisplay";
import "./TargetDossierHeader.css";

/** Dossier facts stay complete; only secondary identity metadata is disclosed. */
export function TargetDossierHeader({
  profile,
  returnedEvidenceCount,
  onOpenProvenance,
}: {
  profile: TargetProfile;
  returnedEvidenceCount: number;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  const text = useMessages(targetDossierMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const identity = targetDisplayIdentity({
    name: profile.entity.name,
    description: profile.entity.description,
    geneSymbol: profile.gene_symbol,
  });
  const stats = [
    { label: text("活性记录"), value: profile.activity_count },
    { label: text("转化证据"), value: profile.target_evidence_count ?? returnedEvidenceCount },
    { label: text("竞品项目"), value: profile.program_count },
  ];

  return (
    <section className="target-dossier-header" aria-label={text("靶点档案摘要")}>
      <div className="target-title-row">
        <div>
          <div className="target-symbol">
            <Dna size={25} aria-hidden="true" />
          </div>
          <div>
            <h2>{identity.primaryName}</h2>
            {identity.fullName ? <p>{identity.fullName}</p> : null}
            <p>
              {targetClassLabel(profile.target_class)} · {organismLabel(profile.organism)}
            </p>
            <dl className="target-header-identifiers">
              <div>
                <dt>UniProt</dt>
                <dd>{profile.uniprot_accession ?? "--"}</dd>
              </div>
            </dl>
          </div>
        </div>
        {profile.profile_id ? (
          <ProvenanceButton
            selection={{
              resourceType: "target_profile",
              resourceId: profile.profile_id,
              label: text("{name} 靶点档案", { name: profile.entity.name }),
            }}
            onOpen={onOpenProvenance}
          />
        ) : null}
      </div>
      <dl className="target-header-stats">
        {stats.map(({ label, value }) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{number.format(value)}</dd>
          </div>
        ))}
      </dl>
      <div className="target-header-secondary">
        <details className="target-header-details">
          <summary>
            {text("标识与别名")}
            <ChevronDown size={14} aria-hidden="true" />
          </summary>
          <div className="target-header-detail-content">
            <dl className="target-header-identifiers">
              <div>
                <dt>{text("基因符号")}</dt>
                <dd>{profile.gene_symbol ?? "--"}</dd>
              </div>
            </dl>
            <EntityNames entity={profile.entity} />
            <p>{text("本次档案查询时间不代表所有来源的最后更新时间")}</p>
          </div>
        </details>
        <dl className="target-header-query-time">
          <div>
            <dt>{text("查询时间")}</dt>
            <dd title={text("本次档案查询时间不代表所有来源的最后更新时间")}>
              <time dateTime={profile.as_of}>{formatDate(profile.as_of, true)}</time>
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
