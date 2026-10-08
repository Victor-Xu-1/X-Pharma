import { relationshipLabel } from "../../lib/entityPresentation";
import { formattingLocale } from "../../lib/i18n";
import { entityText } from "../../lib/i18n/entity";
import { knowledgeText as text } from "../../lib/i18n/knowledge";

export function knowledgePredicateLabel(predicate: string): string {
  if (predicate === "has_entity_alias") return entityText("别名");
  if (predicate === "has_trial") return text("临床试验记录");
  return relationshipLabel(predicate);
}

export function recordValue(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** A reading projection only; the complete unchanged value remains available. */
export function knowledgeValueSummary(value: unknown): string {
  if (value === null || value === undefined) return text("未提供值");
  if (typeof value !== "object") return String(value);
  const number = new Intl.NumberFormat(formattingLocale());
  if (Array.isArray(value)) return text("{count} 项结构化记录", { count: number.format(value.length) });
  const record = recordValue(value);
  if (!record) return text("结构化记录");
  if (record.fact_kind === "entity_alias" && typeof record.alias === "string") {
    const subject = recordValue(record.subject);
    return `${record.alias}${typeof subject?.name === "string" ? ` · ${subject.name}` : ""}`;
  }
  if (Object.keys(record).length === 1 && "value" in record) return knowledgeValueSummary(record.value);
  return (
    Object.entries(record)
      .map(([key, field]) => {
        if (key === "name" && typeof field === "string") return field;
        if (field === null) return `${key}: null`;
        if (Array.isArray(field)) return text("{key}: {count} 项", { key, count: number.format(field.length) });
        if (typeof field === "object")
          return text("{key}: {count} 个字段", { key, count: number.format(Object.keys(field).length) });
        return `${key}: ${String(field)}`;
      })
      .join(" · ") || text("空结构化记录")
  );
}

export function publicKnowledgeMarkdown(markdown: string): string {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  if (lines[0]?.trim() !== "---") return markdown;
  const end = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
  if (end < 2 || !lines.slice(1, end).some((line) => /^[A-Za-z_][\w-]*\s*:/.test(line))) return markdown;
  return lines
    .slice(end + 1)
    .join("\n")
    .trimStart();
}

export function publicKnowledgeLink(url: string): string {
  if (/^#[\w-]+$/.test(url)) return url;
  try {
    const parsed = new URL(url);
    return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : "";
  } catch {
    return "";
  }
}
