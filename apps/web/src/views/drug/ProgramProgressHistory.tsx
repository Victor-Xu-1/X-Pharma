import { formatDate } from "../../components/common";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../../lib/i18n/programVocabulary";
import { geographyLabel } from "./programPresentation";
import type { DrugProgram } from "./types";
import { programStatusLabels } from "./vocabulary";

export function ProgramProgressHistory({ program }: { program: DrugProgram }) {
  const events = [
    ...(program.status_history ?? []).map((event) => ({
      date: event.effective_at,
      geography: event.geography,
      key: `status-${event.phase}-${event.effective_at}-${event.geography ?? "global"}`,
      label: `${phaseLabel(event.phase)}${event.status ? ` · ${controlledDrugLabel(event.status, programStatusLabels)}` : ""}`,
      detail: event.reason,
    })),
    ...(program.milestones ?? []).map((event) => ({
      date: event.occurred_at,
      geography: event.geography,
      key: `milestone-${event.milestone_type}-${event.occurred_at}-${event.title}`,
      label: event.title,
      detail: event.description,
    })),
  ].sort((left, right) => right.date.localeCompare(left.date));
  if (!events.length) return <span>{t("暂无带日期的进度")}</span>;
  return (
    <details className="program-history">
      <summary>{t("{count} 条阶段与里程碑", { count: events.length })}</summary>
      <ol>
        {events.map((event) => (
          <li key={event.key}>
            <strong>{event.label}</strong> · {formatDate(event.date)} · {geographyLabel(event.geography)}
            {event.detail ? <small>{event.detail}</small> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}
