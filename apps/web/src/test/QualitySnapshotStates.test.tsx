import { screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { DataQualitySnapshot } from "../lib/contracts/governance";
import {
  loadDataQualityCoverage,
  loadDataQualityIssues,
  loadDataQualityOwners,
  loadDataQualitySnapshots,
} from "../lib/contracts/governance";
import { QualityTestHarness } from "./QualityTestHarness";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", async (original) => ({
  ...(await original<typeof import("../lib/contracts/governance")>()),
  loadDataQualitySnapshots: vi.fn(),
  loadDataQualityCoverage: vi.fn(),
  loadDataQualityIssues: vi.fn(),
  loadDataQualityOwners: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(loadDataQualityCoverage).mockResolvedValue([]);
  vi.mocked(loadDataQualityIssues).mockResolvedValue([]);
  vi.mocked(loadDataQualityOwners).mockResolvedValue([]);
});
it("does not claim an empty snapshot or an assumed definition version while a read is pending", async () => {
  vi.mocked(loadDataQualitySnapshots).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<QualityTestHarness />);
  await screen.findByText("正在读取质量快照");
  expect(screen.queryByText("尚无质量快照")).not.toBeInTheDocument();
  expect(screen.queryByText(/quality-v1/)).not.toBeInTheDocument();
});
it("does not render a failed snapshot read as an empty successful measurement", async () => {
  vi.mocked(loadDataQualitySnapshots).mockRejectedValue(new Error("RAW_QUALITY_SNAPSHOT_FAILURE"));
  renderWithQueryClient(<QualityTestHarness />);
  await screen.findByText("RAW_QUALITY_SNAPSHOT_FAILURE");
  expect(screen.queryByText("尚无质量快照")).not.toBeInTheDocument();
});
it("keeps missing measurement distinct from observed zero and retains unknown metric records", async () => {
  const snapshot: DataQualitySnapshot = {
    id: "controlled-snapshot",
    trigger: "manual",
    definitions_version: "raw-definitions-v1",
    window_start: "2026-10-10T00:00:00Z",
    window_end: "2026-10-10T00:01:00Z",
    measured_at: "2026-10-10T00:01:00Z",
    created_at: "2026-10-10T00:01:00Z",
    metrics: {
      completeness: {
        label: "原始完整率",
        value: null,
        applicable: true,
        threshold: null,
        comparison: "UNKNOWN_OPERATOR",
      },
      drift: { label: "原始漂移", value: 0, applicable: true, threshold: 0.1, comparison: "lte" },
      RAW_NEW_METRIC: {
        label: "原始新增指标",
        value: 0.0000001,
        applicable: true,
        threshold: 0.0000002,
        comparison: "gte",
      },
    },
  };
  vi.mocked(loadDataQualitySnapshots).mockResolvedValue([snapshot]);
  renderWithQueryClient(<QualityTestHarness />);
  await screen.findByRole("columnheader", { name: "原始新增指标" });
  expect(screen.getAllByText("未上报").length).toBeGreaterThan(0);
  const cards = document.querySelector(".quality-metric-grid");
  if (!(cards instanceof HTMLElement)) throw new Error("Quality metric cards are missing");
  expect(within(cards).getAllByText("0.0%").length).toBe(1);
  expect(within(cards).getByText("1e-7")).toBeInTheDocument();
  expect(within(cards).queryByText("0.00001%")).not.toBeInTheDocument();
  expect(within(cards).getByText("完整率").closest("article")).not.toHaveTextContent("0.0%");
});
