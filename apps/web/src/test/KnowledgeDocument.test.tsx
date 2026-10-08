import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { KnowledgeDocument } from "../views/knowledge/KnowledgeDocument";
import { KnowledgeFactValue } from "../views/knowledge/KnowledgeFactValue";
import {
  knowledgeValueSummary,
  publicKnowledgeLink,
  publicKnowledgeMarkdown,
} from "../views/knowledge/knowledgeReading";

describe("public knowledge reading", () => {
  it("localizes the reader while retaining open supplementary fields, source Markdown and recorded precision", () => {
    const value = {
      fact_kind: "trial",
      registry_id: "NCT1003",
      overall_status: "COMPLETED",
      phases: ["PHASE2", "FUTURE_PHASE"],
      enrollment: 0,
      completion_date: "2028-02-01T00:00:00Z",
      completion_date_precision: "month",
      result_evaluation: false,
    };
    const source = `## Evidence\n\n- **has_trial**: \`${JSON.stringify(value)}\` [^1]\n\n[^1]: 原始引用 / Exact source`;
    render(<KnowledgeDocument markdown={source} title="原始专题标题" />);
    fireEvent.click(screen.getByRole("button", { name: "展开其余 1 个字段" }));
    fireEvent.click(screen.getByText("查看公开原文 Markdown", { selector: "summary" }));
    act(() => setLocale("en"));
    expect(screen.getByRole("heading", { name: "Recorded facts" })).toBeVisible();
    expect(screen.getByText("Clinical trial record", { selector: "strong" })).toBeVisible();
    expect(screen.getByText("Completed", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("Phase II, FUTURE_PHASE", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("2028-02", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("0", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("false", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Collapse supplementary fields" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("textbox", { name: "Complete public original for this version" })).toHaveValue(source);
    expect(screen.getByRole("textbox", { name: "Complete public original for this version" })).toBeVisible();
    expect(screen.getByText("原始引用 / Exact source")).toBeVisible();
  });
  it("reads registered clinical enums and date precision without manufacturing exact dates or changing the original", () => {
    const value = {
      fact_kind: "trial",
      registry_id: "NCT1002",
      overall_status: "COMPLETED",
      phases: ["PHASE1", "PHASE2", "FUTURE_PHASE"],
      enrollment: 0,
      enrollment_type: "ACTUAL",
      start_date: "2015-12-11T00:00:00Z",
      start_date_precision: "day",
      completion_date: "2028-02-01T00:00:00Z",
      completion_date_precision: "month",
    };
    const source = `## Evidence\n\n- **has_trial**: \`${JSON.stringify(value)}\``;
    render(<KnowledgeDocument markdown={source} title="Exact trial snapshot" />);
    expect(screen.getByText("已完成", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("I 期、II 期、FUTURE_PHASE", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("实际人数", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("2015年12月11日", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("2028年02月", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("月", { selector: ".knowledge-value-field-value" })).toBeVisible();
    fireEvent.click(screen.getByText("查看公开原文 Markdown", { selector: "summary" }));
    expect(screen.getByLabelText("此版本的完整公开原文")).toHaveValue(source);
  });
  it("presents a trial snapshot as labelled researcher-facing fields and keeps zero and supplementary values", () => {
    const value = {
      fact_kind: "trial",
      registry_id: "NCT1001",
      overall_status: "COMPLETED",
      phases: ["PHASE2"],
      enrollment: 0,
      conditions: ["Asthma"],
      result_evaluation: false,
    };
    const source = `## Evidence\n\n- **has_trial**: \`${JSON.stringify(value)}\``;
    render(<KnowledgeDocument markdown={source} title="Reviewed trial" />);
    expect(screen.getByText("临床试验记录", { selector: "strong" })).toBeVisible();
    expect(screen.getByText("试验状态")).toBeVisible();
    expect(screen.getByText("已完成", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("0", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("Asthma", { selector: ".knowledge-value-field-value" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "展开其余 1 个字段" }));
    expect(screen.getByText("false", { selector: ".knowledge-value-field-value" })).toBeVisible();
    fireEvent.click(screen.getByText("查看公开原文 Markdown", { selector: "summary" }));
    expect(screen.getByLabelText("此版本的完整公开原文")).toHaveValue(source);
  });
  it("keeps unknown prototype-like heading and emphasis labels literal", () => {
    render(<KnowledgeDocument markdown={"## constructor\n\n**constructor**"} title="Unknown labels" />);
    expect(screen.getByRole("heading", { name: "constructor" })).toBeVisible();
    expect(screen.getByText("constructor", { selector: "strong" })).toBeVisible();
  });
  it.each([
    "javascript:alert(1)",
    "data:text/html,test",
    "file:///tmp/local",
    "//example.org/private",
    "/api/v1/private",
    "https://user:secret@example.org/source",
    "mailto:user@example.org",
  ])("does not activate unsupported URL %s", (url) => {
    expect(publicKnowledgeLink(url)).toBe("");
  });
  it.each(["https://example.org/source?q=1", "http://example.org/source", "#knowledge-note-1"])(
    "retains safe reference %s",
    (url) => {
      expect(publicKnowledgeLink(url)).toBe(url);
    },
  );
  it("removes only valid compiler metadata and does not eat a document's horizontal rule", () => {
    expect(publicKnowledgeMarkdown("---\nid: internal\n---\n\n# Public title")).toBe("# Public title");
    const source = "---\nA non-metadata introduction\n---\nContent";
    expect(publicKnowledgeMarkdown(source)).toBe(source);
    expect(publicKnowledgeMarkdown("---\nid: incomplete")).toBe("---\nid: incomplete");
  });
  it.each([0, false, "", { value: 0 }, { value: false }])(
    "retains the scalar value %j rather than treating it as missing",
    (value) => {
      const expected = typeof value === "object" ? String(value.value) : String(value);
      expect(knowledgeValueSummary(value)).toBe(expected);
    },
  );
  it("keeps all unknown fields available and does not treat an array or empty object as an absent value", () => {
    const value = { name: "Reviewed record", qualifying_data: { accepted: false }, observations: [0, false] };
    render(<KnowledgeFactValue value={value} objectName={null} />);
    expect(screen.getByText("Reviewed record", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("accepted: false", { selector: ".knowledge-value-field-value" })).toBeVisible();
    expect(screen.getByText("0、false", { selector: ".knowledge-value-field-value" })).toBeVisible();
    fireEvent.click(screen.getByText("原始结构化记录", { selector: "summary" }));
    const raw = screen.getByLabelText("完整原始结构化值");
    expect(raw).toHaveValue(JSON.stringify(value, null, 2));
    expect(knowledgeValueSummary([])).toBe("0 项结构化记录");
    expect(knowledgeValueSummary({})).toBe("空结构化记录");
  });
  it("keeps malformed and fenced code literal and the complete public document reachable", () => {
    const source = ["# Public title", "`{not JSON}`", "", "```json", '{"value":0}', "```"].join("\n");
    render(<KnowledgeDocument markdown={source} title="Public title" />);
    expect(screen.getByText("{not JSON}", { selector: "code" })).toBeVisible();
    expect(screen.getByText('{"value":0}', { selector: "code" })).toBeVisible();
    fireEvent.click(screen.getByText("查看公开原文 Markdown", { selector: "summary" }));
    expect(screen.getByLabelText("此版本的完整公开原文")).toHaveValue(source);
  });
  it("gives simultaneously rendered citation lists distinct IDs and complete local reference targets", () => {
    render(
      <>
        <KnowledgeDocument markdown={"First note[^1]\n\n[^1]: First source"} title="First" />
        <KnowledgeDocument markdown={"Second note[^1]\n\n[^1]: Second source"} title="Second" />
      </>,
    );
    const ids = [...document.querySelectorAll<HTMLElement>("[id]")].map((node) => node.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const link of screen.getAllByRole("link")) {
      const target = link.getAttribute("href");
      if (target?.startsWith("#")) expect(document.getElementById(target.slice(1))).not.toBeNull();
      const description = link.getAttribute("aria-describedby");
      if (description) expect(document.getElementById(description)).toHaveTextContent("引用与来源");
    }
  });
  it("summarizes compiled alias values while retaining their unmodified public source and citation", () => {
    const value = {
      fact_kind: "entity_alias",
      subject: { name: "Reviewed Drug" },
      alias: "AC-0010",
      citation: { confidence: 0 },
    };
    const source = `# Reviewed Drug\n\n## Evidence\n\n- **has_entity_alias**: \`${JSON.stringify(value)}\` [^1]\n\n[^1]: Exact source`;
    render(<KnowledgeDocument markdown={source} title="Reviewed Drug" />);
    expect(screen.getByRole("heading", { name: "已记录要点" })).toBeVisible();
    expect(screen.getByText("别名", { selector: "strong" })).toBeVisible();
    expect(screen.getByText("AC-0010 · Reviewed Drug")).toBeVisible();
    const originals = screen.getByText("查看公开原文 Markdown", { selector: "summary" }).parentElement;
    if (!originals) throw new Error("Expected the original public-document disclosure");
    fireEvent.click(within(originals).getByText("查看公开原文 Markdown", { selector: "summary" }));
    expect(within(originals).getByLabelText("此版本的完整公开原文")).toHaveValue(source);
  });
});
