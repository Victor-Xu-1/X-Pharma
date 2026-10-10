import type { Page } from "@playwright/test";
import type { DataQualityIssueRead, DataQualitySnapshotRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";
export const qualityIssue: DataQualityIssueRead = {
  id: "315a81e1-5555-4444-8888-111111111111",
  metric_key: "completeness",
  scope_type: "tenant",
  scope_id: null,
  status: "open",
  severity: "high",
  title: "原始质量记录 A",
  description: "Original source description <EGFR>",
  actual_value: 0.82,
  threshold_value: 0.95,
  comparison: "gte",
  owner_user_id: null,
  owner_display_name: null,
  sla_due_at: "2030-01-01T00:00:00Z",
  detected_at: "2026-10-10T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  resolution_notes: null,
  version: 1,
  last_snapshot_id: "controlled-quality-snapshot",
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
export const qualitySnapshot: DataQualitySnapshotRead = {
  id: "controlled-quality-snapshot",
  trigger: "manual",
  definitions_version: "ORIGINAL_DEFINITIONS",
  measured_at: qualityIssue.created_at,
  created_at: qualityIssue.created_at,
  window_start: qualityIssue.created_at,
  window_end: qualityIssue.created_at,
  metrics: {
    completeness: { value: null, applicable: true, label: "原始完整率", comparison: "gte", threshold: 0.95 },
    drift: { value: 0, applicable: true, label: "原始漂移", comparison: "lte", threshold: 0.1 },
    ORIGINAL_METRIC: { value: 0.0000001, applicable: true, label: "原始新增指标", threshold: 0.0000002 },
  },
};
export async function installQualityFixture(page: Page) {
  const base = await installGovernanceFixture(page);
  const state = {
    issues: [qualityIssue, { ...qualityIssue, id: "315a81e1-5555-4444-8888-222222222222", title: "原始质量记录 B" }],
    reads: 0,
    hold: false,
    denied: false,
    release: undefined as (() => void) | undefined,
    writes: [] as unknown[],
  };
  await page.route("**/api/v1/governance/quality/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      state.reads++;
      if (path.endsWith("/snapshots")) return route.fulfill({ json: [qualitySnapshot] });
      if (path.endsWith("/coverage")) return route.fulfill({ json: [] });
      if (path.endsWith("/owners"))
        return route.fulfill({ json: [{ id: "controlled-owner", display_name: "Original owner", role: "analyst" }] });
      if (path.endsWith("/issues"))
        return state.denied
          ? route.fulfill({ status: 403, json: { detail: "RAW_QUALITY_DENIAL" } })
          : route.fulfill({ json: state.issues });
      if (path.endsWith("/events")) return route.fulfill({ json: [] });
    }
    if (request.method() === "POST" && path.endsWith("/actions")) {
      state.writes.push(request.postDataJSON());
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      const changed = {
        ...state.issues[0],
        owner_user_id: "controlled-owner",
        owner_display_name: "Original owner",
        version: 2,
      };
      state.issues[0] = changed;
      return route.fulfill({ json: changed });
    }
    throw new Error("Unexpected controlled quality request: " + request.method() + " " + path);
  });
  return { base, state };
}
