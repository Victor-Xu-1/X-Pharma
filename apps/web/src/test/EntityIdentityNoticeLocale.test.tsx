import { act, render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { EntityIdentityNotice } from "../components/EntityIdentityNotice";
import { setLocale } from "../lib/i18n";

beforeEach(() => setLocale("en"));
it("localizes the scope label while preserving an original provider note verbatim", () => {
  const note = "原始注册说明 <source>";
  render(
    <EntityIdentityNotice
      entity={{ entity_type: "organization", attributes: { identity_scope: "provider_label", identity_note: note } }}
    />,
  );
  expect(screen.getByRole("note", { name: "Source name scope" })).toHaveTextContent(note);
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("note", { name: "来源名称范围" })).toHaveTextContent(note);
});
it("updates the project-owned fallback caveat on standalone locale switching", () => {
  render(
    <EntityIdentityNotice entity={{ entity_type: "organization", attributes: { identity_scope: "provider_label" } }} />,
  );
  expect(screen.getByText(/A registry sponsor name/)).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("注册平台的申办方名称，不代表已核实的法律主体或企业集团归并。")).toBeInTheDocument();
});
it("does not add a provider caveat to a canonical organization", () => {
  render(
    <EntityIdentityNotice
      entity={{ entity_type: "organization", attributes: { identity_note: "Source-owned metadata" } }}
    />,
  );
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
});
