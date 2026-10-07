import { KnowledgeStructuredValue } from "./KnowledgeStructuredValue";

export function KnowledgeFactValue({ value, objectName }: { value: unknown; objectName: string | null }) {
  const structured = value !== null && typeof value === "object";
  return (
    <div className="knowledge-fact-value">
      {objectName ? <span>{objectName}</span> : <KnowledgeStructuredValue value={value} />}
      {structured ? (
        <details className="knowledge-original-value">
          <summary>原始结构化记录</summary>
          <textarea
            className="knowledge-source-text"
            rows={8}
            readOnly
            aria-label="完整原始结构化值"
            value={JSON.stringify(value, null, 2)}
          />
        </details>
      ) : null}
    </div>
  );
}
