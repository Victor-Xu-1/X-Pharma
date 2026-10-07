import { describe, expect, it } from "vitest";
import { knowledgeFields } from "../views/knowledge/knowledgeFields";
import { knowledgeTypeLabel } from "../views/knowledge/knowledgeTypes";

describe("registered knowledge display boundaries", () => {
  it.each([
    ["2028-02-01T00:00:00Z", "year", "2028年"],
    ["2028-02", "month", "2028年02月"],
    ["2028", "year", "2028年"],
    ["2028T00:00:00Z", "year", "2028T00:00:00Z"],
    ["2028-02T00:00:00Z", "month", "2028-02T00:00:00Z"],
    ["2025-02-30T00:00:00Z", "day", "2025-02-30T00:00:00Z"],
    ["2028-13", "month", "2028-13"],
    ["2028", "day", "2028"],
    ["2028-02-01T00:00:00Z", null, "2028-02-01T00:00:00Z"],
    ["2028-02-01T00:00:00Z", "uncertain", "2028-02-01T00:00:00Z"],
    ["2028-02-01T00:00:00+05:00", "day", "2028-02-01T00:00:00+05:00"],
    ["2028-02-01T12:30:00Z", "day", "2028-02-01T12:30:00Z"],
  ])("respects %s and %s without inventing precision or changing timezone", (value, precision, expected) => {
    const fields = knowledgeFields({ fact_kind: "trial", start_date: value, start_date_precision: precision });
    expect(fields?.primary.find((field) => field.key === "start_date")?.value).toBe(expected);
  });
  it("keeps unknown clinical codes, empty arrays and false literal", () => {
    const fields = knowledgeFields({
      fact_kind: "trial",
      overall_status: "FUTURE_STATUS",
      phases: ["PHASE2", "FUTURE_PHASE"],
      enrollment: false,
      conditions: [],
      enrollment_type: "constructor",
    });
    const values = Object.fromEntries(fields?.primary.map((field) => [field.key, field.value]) ?? []);
    expect(values).toEqual({
      overall_status: "FUTURE_STATUS",
      phases: "II 期、FUTURE_PHASE",
      enrollment: "false",
      conditions: "0 项",
      enrollment_type: "constructor",
    });
  });
  it.each(["constructor", "__proto__", "toString", "custom_provider_type"])(
    "keeps unknown topic type %s literal",
    (value) => {
      expect(knowledgeTypeLabel(value)).toBe(value);
    },
  );
});
