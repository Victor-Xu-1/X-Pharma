import { expect, it } from "vitest";
import type { IngestionRun } from "../lib/contracts/dataFactory";
import { setLocale } from "../lib/i18n";
import { runVersionProgressLabel } from "../views/dataFactory/RunStagePresentation";

const run: IngestionRun = {
  id: "controlled-run",
  workflow_id: "Original workflow",
  data_source_id: "controlled-source",
  state: "running",
  effective_state: "running",
  cancelable: true,
  cancel_requested_at: null,
  total_versions: 0,
  completed_versions: 0,
  counters: { discovered: 3 },
  progress_percent: 10,
  stages: [{ stage: "discovery", status: "running", total_items: 3, completed_items: 0, failed_items: 0 }],
  result: {},
  error_summary: null,
  created_at: "2026-10-01T00:00:00Z",
  started_at: null,
  heartbeat_at: null,
  completed_at: null,
  temporal_run_id: null,
  temporal_workflow_id: null,
};

it("does not turn running discovery with zero snapshots into a completed no-new-version claim", () => {
  setLocale("en");
  expect(runVersionProgressLabel(run)).toBe("Discovering versions · 3 objects observed");
  setLocale("zh-CN");
  expect(runVersionProgressLabel(run)).toBe("正在发现版本 · 已观测 3 个对象");
});

it("keeps a failed zero-version run distinct from successful discovery completion", () => {
  setLocale("en");
  expect(runVersionProgressLabel({ ...run, state: "failed", effective_state: "failed" })).toBe(
    "Version processing did not complete · 3 objects observed",
  );
});

it("retains observed terminal no-new-version and exact completed-version counts", () => {
  setLocale("en");
  expect(runVersionProgressLabel({ ...run, state: "succeeded", effective_state: "succeeded" })).toBe(
    "3 objects checked · no new versions in this run",
  );
  expect(runVersionProgressLabel({ ...run, total_versions: 3, completed_versions: 0 })).toBe("0/3 versions completed");
});
