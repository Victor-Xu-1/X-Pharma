import { act, fireEvent, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { emptyDealSearchFilters } from "../lib/contracts/deals";
import type { EntityRead } from "../lib/generated";
import { DealParticipantFilters } from "../views/deals/DealParticipantFilters";
import { renderWithQueryClient } from "./renderWithQueryClient";

const organization: EntityRead = {
  id: "11111111-1111-4111-8111-111111111111",
  canonical_entity_id: "11111111-1111-4111-8111-111111111111",
  entity_type: "organization",
  name: "Browser-only organization",
  description: null,
  attributes: {},
  external_ids: {},
  review_status: "verified",
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
};

function renderParticipants(candidate: EntityRead = organization) {
  const onChooseParty = vi.fn();
  const onPartyText = vi.fn();
  const submit = vi.fn();
  renderWithQueryClient(
    <form onSubmit={submit}>
      <DealParticipantFilters
        filters={{ ...emptyDealSearchFilters, party: organization.name }}
        facets={{}}
        suggestions={[candidate]}
        suggestionsEnabled
        loading={false}
        onChange={vi.fn()}
        onPartyText={onPartyText}
        onChooseParty={onChooseParty}
      />
      <button type="button">其他筛选</button>
    </form>,
  );
  return { input: screen.getByRole("combobox", { name: "参与机构" }), onChooseParty, onPartyText, submit };
}

it("does not open a restored free-text party suggestion menu without input interaction", () => {
  const { input } = renderParticipants();
  expect(input).toHaveValue(organization.name);
  expect(input).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("dismisses suggestions when focus leaves the field without clearing the party condition", () => {
  const { input, onPartyText } = renderParticipants();
  fireEvent.focus(input);
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  fireEvent.blur(input, { relatedTarget: screen.getByRole("button", { name: "其他筛选" }) });
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(input).toHaveValue(organization.name);
  expect(onPartyText).not.toHaveBeenCalled();
});

it("keeps keyboard focus inside the active suggestion menu and restores input focus after choosing", () => {
  const { input, onChooseParty, submit } = renderParticipants();
  act(() => input.focus());
  fireEvent.keyDown(input, { key: "ArrowDown" });
  const option = screen.getByRole("option", { name: organization.name });
  expect(option).toHaveFocus();
  fireEvent.click(option);
  expect(onChooseParty).toHaveBeenCalledWith(organization.id, organization.name);
  expect(input).toHaveFocus();
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(submit).not.toHaveBeenCalled();
});

it("consumes Escape only for an open menu and preserves text editing", () => {
  const { input, onChooseParty } = renderParticipants();
  act(() => input.focus());
  fireEvent.keyDown(input, { key: "Escape" });
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(input).toHaveFocus();
  expect(input).toHaveValue(organization.name);
  expect(onChooseParty).not.toHaveBeenCalled();
});

it("reopens suggestions on a deliberate click after Escape without changing the condition", () => {
  const { input, onPartyText } = renderParticipants();
  act(() => input.focus());
  fireEvent.keyDown(input, { key: "Escape" });
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  fireEvent.click(input);
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  expect(input).toHaveValue(organization.name);
  expect(onPartyText).not.toHaveBeenCalled();
});

it("keeps the combobox label stable when candidate text is rendered", () => {
  const { input } = renderParticipants();
  fireEvent.focus(input);
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "参与机构" })).toBe(input);
});

it("does not reserve an empty metadata row when a candidate has no external identifiers", () => {
  const { input } = renderParticipants();
  fireEvent.focus(input);
  const option = screen.getByRole("option", { name: organization.name });
  expect(option.querySelector("small")).not.toBeInTheDocument();
});

it("preserves the full organization name and its actual external identifiers", () => {
  const { input } = renderParticipants({ ...organization, external_ids: { ror: "03yrm5c26", wikidata: "Q123" } });
  fireEvent.focus(input);
  const option = screen.getByRole("option", { name: `${organization.name} · 03yrm5c26 · Q123` });
  expect(option.querySelector("span")).toHaveTextContent(organization.name);
  expect(option.querySelector("small")).toHaveTextContent("03yrm5c26 · Q123");
});
