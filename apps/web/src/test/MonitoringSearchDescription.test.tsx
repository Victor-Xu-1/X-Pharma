import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { SavedSearch } from "../lib/contracts/monitoring";
import { MonitoringSearches } from "../views/monitoring/MonitoringSearches";

function renderDescription(description: string) {
  const saved: SavedSearch = {
    id: "search-1",
    owner_user_id: "another-user",
    name: "Shared research",
    description,
    query_type: "entity_search",
    query_version: 1,
    query_json: { q: "EGFR" },
    visibility: "tenant",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  };
  const edit = vi.fn();
  const share = vi.fn();
  const replay = vi.fn();
  render(
    <MonitoringSearches
      searches={[saved]}
      userId="reader"
      pending={new Set()}
      onReplay={replay}
      onEdit={edit}
      onVisibilityChange={share}
    />,
  );
  return { edit, share, replay };
}

it("lets a shared read-only researcher expand the complete business description without a mutation", () => {
  const description = "完整研究范围、来源边界与团队约定。".repeat(40);
  const actions = renderDescription(description);
  const summary = screen.getByText("业务说明");
  const details = summary.closest("details");
  expect(details).not.toBeNull();
  expect(details).not.toHaveAttribute("open");
  fireEvent.click(summary);
  expect(details).toHaveAttribute("open");
  expect(screen.getByText(description)).toBeVisible();
  expect(screen.queryByRole("button", { name: /编辑|共享 Shared research/ })).not.toBeInTheDocument();
  for (const callback of Object.values(actions)) expect(callback).not.toHaveBeenCalled();
});

it("renders literal note text safely instead of introducing a rich-text or HTML parser", () => {
  const description = '<img src=x onerror="alert(1)"> 原文约束\n第二行说明';
  renderDescription(description);
  fireEvent.click(screen.getByText("业务说明"));
  const details = screen.getByText("业务说明").closest("details");
  expect(details?.querySelector("p")?.textContent).toBe(description);
  expect(details?.querySelector("img")).toBeNull();
});

it("does not add an empty disclosure when no business description was supplied", () => {
  renderDescription("");
  expect(screen.queryByText("业务说明")).not.toBeInTheDocument();
});
