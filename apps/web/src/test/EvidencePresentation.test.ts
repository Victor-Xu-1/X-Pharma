import { expect, it } from "vitest";
import type { EvidenceChunk } from "../lib/contracts/evidence";
import { publicSourceUrl, sourceLocator } from "../lib/evidencePresentation";
import { setLocale } from "../lib/i18n";

function chunk(positions: unknown[], metadata: Record<string, unknown> = {}): EvidenceChunk {
  return {
    content: "原始证据 · EGFR",
    document_id: "original-id",
    document_name: "原始文档",
    dataset_id: "source-owned",
    positions,
    metadata,
    similarity: null,
  };
}

it("keeps raw citation data unchanged while formatting zero coordinates and known locator kinds", () => {
  const value = chunk([{ page: 0, row: 0, line: 7, start_char: 0, end_char: 12 }]);
  const original = JSON.stringify(value);
  setLocale("en");
  expect(sourceLocator(value)).toBe("Page 0 · Row 0 · Line 7 · Characters 0-12");
  setLocale("zh-CN");
  expect(sourceLocator(value)).toBe("页 0 · 行 0 · 文本行 7 · 字符 0-12");
  expect(JSON.stringify(value)).toBe(original);
});

it("retains unknown source locator names verbatim and does not invent a missing location", () => {
  setLocale("en");
  expect(sourceLocator(chunk([{ locator_kind: "原始定位键", locator_value: "A12" }]))).toBe("原始定位键 A12");
  expect(sourceLocator(chunk([]))).toBe("The source did not provide a page or paragraph location");
});

it.each(["javascript:alert(1)", "file:///private/source", "https://user:secret@example.test/source", 42])(
  "does not expose unsafe source link %s",
  (source) => expect(publicSourceUrl(chunk([], { source }))).toBeNull(),
);

it("retains the original authorized public source URL", () => {
  expect(publicSourceUrl(chunk([], { source: "https://example.test/original?record=1" }))).toBe(
    "https://example.test/original?record=1",
  );
});
