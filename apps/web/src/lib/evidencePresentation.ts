import type { EvidenceChunk } from "./contracts/evidence";
import { type evidenceMessages, evidenceText as t } from "./i18n/evidence";

function primitiveLocator(value: unknown): string | null {
  if (typeof value === "string") return value.trim().slice(0, 120) || null;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

export function sourceLocator(chunk: EvidenceChunk): string {
  const labels: Record<string, keyof typeof evidenceMessages> = {
    page: "页",
    page_number: "页",
    slide: "幻灯片",
    sheet: "工作表",
    row: "行",
    paragraph: "段落",
    section: "章节",
    line: "文本行",
  };
  const values: string[] = [];
  const add = (key: string, value: unknown) => {
    const normalized = primitiveLocator(value);
    if (!normalized) return;
    const display = `${labels[key] ? t(labels[key]) : key} ${normalized}`;
    if (!values.includes(display)) values.push(display);
  };
  for (const position of chunk.positions) {
    if (!position || typeof position !== "object" || Array.isArray(position)) continue;
    const record = position as Record<string, unknown>;
    const locatorKind = primitiveLocator(record.locator_kind);
    const locatorValue = primitiveLocator(record.locator_value);
    if (locatorKind && locatorValue) add(locatorKind, locatorValue);
    for (const key of ["page", "page_number", "slide", "sheet", "row", "paragraph", "section", "line"])
      add(key, record[key]);
    const startChar = primitiveLocator(record.start_char);
    const endChar = primitiveLocator(record.end_char);
    if (startChar && endChar) {
      const characterRange = t("字符 {start}-{end}", { start: startChar, end: endChar });
      if (!values.includes(characterRange)) values.push(characterRange);
    }
  }
  if (!values.length) {
    for (const key of ["page", "page_number", "slide", "sheet", "row", "paragraph", "section", "line"])
      add(key, chunk.metadata[key]);
  }
  return values.slice(0, 4).join(" · ") || t("来源未提供页码或段落定位");
}

export function publicSourceUrl(chunk: EvidenceChunk): string | null {
  const value = chunk.metadata.source;
  if (typeof value !== "string") return null;
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : null;
  } catch {
    return null;
  }
}
