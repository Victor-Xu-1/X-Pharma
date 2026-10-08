import { ArrowRight, RotateCcw } from "lucide-react";
import { useMessages } from "../lib/i18n";
import { professionalQueryLabel, professionalQueryMessages } from "../lib/i18n/professionalQuery";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { createProfessionalSearchDraft } from "../lib/professionalSearch";
import type { WorkspaceLocation } from "../lib/workspaceRouting";
import { DealsFields } from "./professionalQuery/deals";
import { EpidemiologyFields } from "./professionalQuery/epidemiology";
import { NewsFields } from "./professionalQuery/news";
import { PatentsFields } from "./professionalQuery/patents";
import { PipelineFields } from "./professionalQuery/pipeline";
import { domains } from "./professionalQuery/presentation";
import { RegulatoryFields } from "./professionalQuery/regulatory";
import { TrialsFields } from "./professionalQuery/trials";
import { useProfessionalQueryModel } from "./professionalQuery/useProfessionalQueryModel";

/** Coordinates the single draft; domain fields own only presentation. */
export function ProfessionalQueryBuilder({
  query,
  onExecute,
}: {
  query: string;
  onExecute: (location: WorkspaceLocation) => void;
}) {
  const t = useMessages(professionalQueryMessages);
  const model = useProfessionalQueryModel(query, onExecute);
  const { selected, conditionCount, draft, setDraft, error, selectDomain, execute } = model;
  return (
    <section className="professional-query-builder" aria-labelledby="professional-query-title">
      <header>
        <div>
          <strong id="professional-query-title">{t("专业条件查询")}</strong>
          <span>
            {professionalQueryLabel(selected.label)} ·{" "}
            {conditionCount ? t("已选 {count} 项", { count: conditionCount }) : t("全部记录")}
          </span>
        </div>
        <button
          type="button"
          className="text-button"
          onClick={() => setDraft(createProfessionalSearchDraft(draft.domain, query))}
          disabled={conditionCount === Number(Boolean(query.trim()))}
        >
          <RotateCcw size={14} />
          {t("清除条件")}
        </button>
      </header>

      <nav aria-label={t("专业数据域")}>
        {domains.map(({ value, label, detail, icon: Icon }) => (
          <button
            type="button"
            key={value}
            className={draft.domain === value ? "selected" : ""}
            onClick={() => selectDomain(value)}
            aria-pressed={draft.domain === value}
            title={professionalQueryLabel(detail)}
          >
            <Icon size={15} />
            <span>{professionalQueryLabel(label)}</span>
          </button>
        ))}
      </nav>

      <div className="professional-query-fields">
        {draft.domain === "pipeline" ? <PipelineFields {...model} /> : null}

        {draft.domain === "trials" ? <TrialsFields {...model} /> : null}

        {draft.domain === "patents" ? <PatentsFields {...model} /> : null}

        {draft.domain === "deals" ? <DealsFields {...model} /> : null}

        {draft.domain === "regulatory" ? <RegulatoryFields {...model} /> : null}

        {draft.domain === "epidemiology" ? <EpidemiologyFields {...model} /> : null}

        {draft.domain === "news" ? <NewsFields {...model} /> : null}
      </div>

      <footer>
        <div>
          <strong>{professionalQueryLabel(selected.label)}</strong>
          <span>{query.trim() ? t("关键词：{query}", { query: query.trim() }) : t("未限定关键词")}</span>
        </div>
        {error ? (
          <p className="inline-error" role="alert">
            {professionalValidationText(error)}
          </p>
        ) : null}
        <button className="primary-button" type="button" onClick={execute}>
          {t("查询 {domain}", { domain: professionalQueryLabel(selected.label) })}
          <ArrowRight size={15} />
        </button>
      </footer>
    </section>
  );
}
