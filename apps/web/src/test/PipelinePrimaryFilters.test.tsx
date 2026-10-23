import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { emptyPipelineSearchFilters } from "../lib/contracts/pipeline";
import { PipelinePrimaryFilters } from "../views/pipeline/PipelinePrimaryFilters";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/intelligence", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/contracts/intelligence")>()),
  getEntity: vi.fn().mockRejectedValue(new Error("Controlled entity lookup unavailable")),
}));

it("keeps the primary query visible and reveals exact entity filters only on request", async () => {
  const updateFilter = vi.fn();
  const view = renderWithQueryClient(
    <PipelinePrimaryFilters
      filters={emptyPipelineSearchFilters()}
      updateFilter={updateFilter}
      data={undefined}
      rememberEntity={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("关键词")).toBeVisible();
  expect(screen.getByLabelText("总体最高阶段")).toBeVisible();
  const panel = view.container.querySelector(".pipeline-entity-disclosure");
  expect(panel).not.toBeNull();
  expect(panel).not.toHaveAttribute("open");
  expect(screen.getByRole("group", { name: "药品、靶点、适应症与研发机构" })).not.toBeVisible();
  fireEvent.click(screen.getByText("药品、靶点、适应症与研发机构", { selector: "summary span" }));
  await waitFor(() => expect(panel).toHaveAttribute("open"));
  expect(screen.getByRole("group", { name: "药品、靶点、适应症与研发机构" })).toBeVisible();
  expect(updateFilter).not.toHaveBeenCalled();
});

it("reveals an active exact entity selection even while its lookup is unavailable", async () => {
  const view = renderWithQueryClient(
    <PipelinePrimaryFilters
      filters={{ ...emptyPipelineSearchFilters(), targetEntityId: "target-1" }}
      updateFilter={vi.fn()}
      data={undefined}
      rememberEntity={vi.fn()}
    />,
  );
  const panel = view.container.querySelector(".pipeline-entity-disclosure");
  expect(panel).toHaveAttribute("data-active-count", "1");
  expect(panel).toHaveAttribute("open");
  expect(screen.getByRole("group", { name: "药品、靶点、适应症与研发机构" })).toBeVisible();
  expect(await screen.findByRole("button", { name: "重试已选靶点" })).toBeVisible();
  expect(panel).toHaveAttribute("open");
});
