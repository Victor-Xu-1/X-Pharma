import { ChevronDown } from "lucide-react";
import { Fragment, type ReactNode } from "react";
import "./DossierSummaryFacts.css";

interface SummaryFact {
  key: string;
  label: string;
  value: ReactNode;
}
type FactTriple = readonly [SummaryFact, SummaryFact, SummaryFact];

/** Presentation only; feature owners supply localized labels and unchanged facts. */
export function DossierSummaryFacts({
  primary,
  secondary,
  moreLabel,
}: {
  primary: FactTriple;
  secondary: FactTriple;
  moreLabel: string;
}) {
  function facts(items: FactTriple) {
    return items.map(({ key, label, value }) => (
      <div key={key}>
        <dt>{label}</dt>
        <dd>
          {typeof value === "string"
            ? Array.from(value.matchAll(/[^_/-]+|[_/-]/gu), ({ 0: part, index: sourceOffset }) => (
                <Fragment key={sourceOffset}>
                  {part}
                  {/^[_/-]$/u.test(part) ? <wbr /> : null}
                </Fragment>
              ))
            : value}
        </dd>
      </div>
    ));
  }
  return (
    <>
      <dl className="dossier-metrics company-profile-metrics dossier-summary-primary">{facts(primary)}</dl>
      <details className="dossier-summary-details">
        <summary>
          {moreLabel}
          <ChevronDown size={15} aria-hidden="true" />
        </summary>
        <dl className="dossier-metrics dossier-summary-secondary">{facts(secondary)}</dl>
      </details>
    </>
  );
}
