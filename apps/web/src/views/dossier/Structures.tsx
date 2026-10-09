import { FlaskConical } from "lucide-react";
import { EmptyState } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import type { DossierSectionProps } from "./types";

export function Structures({ data, onOpen }: DossierSectionProps) {
  useLocale();
  if (!data.structures.length) return <EmptyState title={t("暂无关联化学结构")} />;
  return (
    <div className="entity-record-list">
      {data.structures.map((item) => (
        <article key={item.id}>
          <FlaskConical size={18} />
          <div>
            <span>
              {item.molecular_formula ?? t("分子式未记录")} · MW {item.molecular_weight ?? "--"}
            </span>
            <h3 className="mono-cell">{item.standard_inchi_key}</h3>
            <p className="mono-cell">{item.canonical_smiles}</p>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "compound_structure", resourceId: item.id, label: item.standard_inchi_key }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
