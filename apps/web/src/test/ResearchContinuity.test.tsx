import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ResearchContinuity } from "../components/ResearchContinuity";
import { loadRecentResearch } from "../lib/contracts/researchActivity";
import { setLocale } from "../lib/i18n";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/researchActivity", () => ({
  researchActivityKeys: { recent: ["research", "recent-entities"] },
  loadRecentResearch: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(loadRecentResearch).mockResolvedValue([]);
});

it("keeps the recent-research disclosure and cached read when its language changes", async () => {
  const open = vi.fn();
  const { rerender } = renderWithQueryClient(<ResearchContinuity onOpenEntity={open} />);
  fireEvent.click(screen.getByRole("button", { name: "继续最近的研究" }));
  await screen.findByText("暂无最近研究");
  const calls = vi.mocked(loadRecentResearch).mock.calls.length;
  setLocale("en");
  rerender(<ResearchContinuity onOpenEntity={open} />);
  expect(screen.getByRole("button", { name: "Continue recent research" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("No recent research yet")).toBeVisible();
  expect(loadRecentResearch).toHaveBeenCalledTimes(calls);
});

it("loads recent research only when requested and provides an honest empty state", async () => {
  renderWithQueryClient(<ResearchContinuity onOpenEntity={vi.fn()} />);
  expect(loadRecentResearch).not.toHaveBeenCalled();
  const trigger = screen.getByRole("button", { name: "继续最近的研究" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(trigger);
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  await screen.findByText("暂无最近研究");
});

it("opens the stable server-authorized entity rather than a URL supplied by history data", async () => {
  vi.mocked(loadRecentResearch).mockResolvedValue([
    {
      entity: {
        id: "target-id",
        canonical_entity_id: "target-id",
        entity_type: "target",
        name: "EGFR",
        description: "Target",
        review_status: "verified",
        external_ids: {},
        attributes: {},
        identity_identifiers: [],
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-10-01T00:00:00Z",
      },
      visited_at: "2026-10-01T00:00:00Z",
    },
  ]);
  const open = vi.fn();
  renderWithQueryClient(<ResearchContinuity onOpenEntity={open} />);
  fireEvent.click(screen.getByRole("button", { name: "继续最近的研究" }));
  fireEvent.click(await screen.findByRole("button", { name: "继续研究 EGFR" }));
  expect(open).toHaveBeenCalledWith("target-id");
});

it("keeps a failed request separate from an empty history and supports recovery", async () => {
  vi.mocked(loadRecentResearch).mockRejectedValueOnce(new Error("Recent research unavailable"));
  renderWithQueryClient(<ResearchContinuity onOpenEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "继续最近的研究" }));
  await screen.findByText("Recent research unavailable");
  expect(screen.queryByText("暂无最近研究")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  await waitFor(() => expect(screen.getByText("暂无最近研究")).toBeInTheDocument());
});
