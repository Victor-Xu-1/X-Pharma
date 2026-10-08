import { act, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EntityIdentityLabel } from "../components/EntityIdentityLabel";
import { entityIdentityNote, entityTypeLabel, matchExplanation, relationshipLabel } from "../lib/entityPresentation";
import { setLocale } from "../lib/i18n";
import type { Entity } from "../lib/types";

it("localizes controlled entity identity while preserving researcher names and source identity notes", () => {
  const entity = {
    name: "原始登记条件 EGFR",
    entity_type: "disease" as const,
    attributes: { identity_scope: "provider_label", identity_note: "来源原文，不能当作获批适应症。" },
  };
  render(<EntityIdentityLabel entity={entity} />);
  act(() => setLocale("en"));
  expect(screen.getByText("Registry condition")).toBeInTheDocument();
  expect(screen.getByText("来源原文，不能当作获批适应症。")).toBeInTheDocument();
  expect(screen.getByLabelText("Identity details for 原始登记条件 EGFR")).toBeInTheDocument();
  expect(entityIdentityNote(entity)).toBe("来源原文，不能当作获批适应症。");
});

it("distinguishes generic organizations from registry sponsor labels in English", () => {
  setLocale("en");
  expect(entityTypeLabel({ entity_type: "organization", attributes: {} })).toBe("Organization");
  expect(entityTypeLabel({ entity_type: "organization", attributes: { identity_scope: "provider_label" } })).toBe(
    "Registry sponsor",
  );
  expect(entityTypeLabel({ entity_type: "disease", attributes: {} })).toBe("Disease");
  expect(entityIdentityNote({ entity_type: "disease", attributes: { identity_scope: "provider_label" } })).toContain(
    "not an approved indication",
  );
});

it("translates relationship predicates without rewriting unknown identifiers", () => {
  setLocale("en");
  expect(relationshipLabel("has_target")).toBe("Targets");
  expect(relationshipLabel("trial_lead_sponsor")).toBe("Registry lead sponsor");
  expect(relationshipLabel("unmodelled_predicate")).toBe("unmodelled_predicate");
});

it("localizes match explanations while retaining the actual matched value and namespace", () => {
  const entity = {
    match: {
      match_type: "external_id",
      match_relation: "exact",
      namespace: "UniProt",
      matched_value: "P00533 中文来源",
    },
  } as unknown as Entity;
  setLocale("en");
  expect(matchExplanation(entity)).toBe("External identifier · Exact match: UniProt · P00533 中文来源");
  setLocale("zh-CN");
  expect(matchExplanation(entity)).toBe("外部标识精确匹配：UniProt · P00533 中文来源");
});
