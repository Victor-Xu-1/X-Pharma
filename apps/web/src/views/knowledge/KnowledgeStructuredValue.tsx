import { useId, useState } from "react";
import { knowledgeFields } from "./knowledgeFields";
import { knowledgeValueSummary } from "./knowledgeReading";

/** Phrasing elements remain valid inside a Markdown paragraph or list item. */
export function KnowledgeStructuredValue({ value }: { value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const remainingId = useId();
  const fields = knowledgeFields(value);
  if (!fields) return <span className="knowledge-inline-value">{knowledgeValueSummary(value)}</span>;
  const display = (items: typeof fields.primary) =>
    items.map((field) => (
      <span className="knowledge-value-field" key={field.key}>
        <span className="knowledge-value-field-label">{field.label}</span>
        <span className="knowledge-value-field-value">{field.value}</span>
      </span>
    ));
  return (
    <span className="knowledge-structured-value">
      <span className="knowledge-value-fields">{display(fields.primary)}</span>
      {fields.remaining.length ? (
        <>
          <button
            type="button"
            className="secondary-button knowledge-field-toggle"
            aria-expanded={expanded}
            aria-controls={remainingId}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "收起补充字段" : `展开其余 ${fields.remaining.length} 个字段`}
          </button>
          <span id={remainingId} className="knowledge-value-fields knowledge-value-extra" hidden={!expanded}>
            {display(fields.remaining)}
          </span>
        </>
      ) : null}
    </span>
  );
}
