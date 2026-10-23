import type { Page } from "@playwright/test";
import type { ProjectionMaintenanceJobRead, PublicationBatchRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";

const batchId = "815a81e1-5555-4444-8888-777777777777";
export const controlledProjectionJob: ProjectionMaintenanceJobRead = {
  id: "815a81e1-5555-4444-8888-888888888888",
  operation: "consistency_check",
  status: "succeeded",
  requested_by_user_id: "controlled-user",
  attempts: 1,
  worker_id: "CONTROLLED_WORKER",
  lease_expires_at: null,
  build_id: null,
  last_error: null,
  result: { expected_counts: { entities: 12, evidence: 0 }, actual_counts: { evidence: 0 } },
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
  started_at: null,
  completed_at: null,
};
export async function createPublicationFixture(page: Page) {
  const base = await installGovernanceFixture(page);
  return {
    ...base,
    records: [] as PublicationBatchRead[],
    jobs: [] as ProjectionMaintenanceJobRead[],
    batchDenied: false,
    privileged: false,
    accessDenied: false,
    holdPreview: false,
    holdCommit: false,
    holdMaintenance: false,
    releasePreview: undefined as (() => void) | undefined,
    releaseCommit: undefined as (() => void) | undefined,
    releaseMaintenance: undefined as (() => void) | undefined,
  };
}
export type PublicationFixture = Awaited<ReturnType<typeof createPublicationFixture>>;
export async function installPublicationFixture(page: Page, shared?: PublicationFixture) {
  const state = shared ?? (await createPublicationFixture(page));
  if (shared) await installGovernanceFixture(page, shared);
  await page.route("**/api/v1/governance/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (
      path.startsWith("/api/v1/governance/publication-batches") ||
      path.startsWith("/api/v1/governance/projection-maintenance")
    ) {
      if (request.method() === "GET") state.reads[path] = (state.reads[path] ?? 0) + 1;
      else state.writes.push(`${request.method()} ${path}`);
    } else return route.fallback();
    if (path === "/api/v1/governance/publication-batches" && request.method() === "GET")
      return route.fulfill({ json: state.records.map((record) => ({ ...record, items: [] })) });
    if (path === "/api/v1/governance/publication-batches/preview" && request.method() === "POST") {
      const input = request.postDataJSON() as {
        operation: "publish" | "withdraw";
        staged_fact_ids: string[];
        idempotency_key: string;
        reason: string;
      };
      if (state.holdPreview)
        await new Promise<void>((resolve) => {
          state.releasePreview = resolve;
        });
      const record: PublicationBatchRead = {
        id: batchId,
        operation: input.operation,
        status: "previewed",
        preview_sha256: "a".repeat(64),
        idempotency_key: input.idempotency_key,
        expected_count: input.staged_fact_ids.length,
        blocked_count: 0,
        reason: input.reason.trim(),
        requested_by_user_id: "controlled-user",
        committed_by_user_id: null,
        committed_at: null,
        result: { requested_fact_ids: input.staged_fact_ids },
        created_at: "2026-10-10T00:00:00Z",
        updated_at: "2026-10-10T00:00:00Z",
        items: input.staged_fact_ids.map((id, position) => ({
          id: `controlled-item-${position}`,
          staged_fact_id: id,
          position,
          expected_status: "review_pending",
          outcome: "ready",
          blockers: [],
          snapshot: { fact_kind: "program" },
          created_at: "2026-10-10T00:00:00Z",
        })),
      };
      state.records = [record];
      return route.fulfill({ status: 201, json: record });
    }
    if (path === `/api/v1/governance/publication-batches/${batchId}/commit` && request.method() === "POST") {
      if (state.holdCommit)
        await new Promise<void>((resolve) => {
          state.releaseCommit = resolve;
        });
      const record = state.records[0];
      if (!record) return route.fulfill({ status: 404, json: { detail: "CONTROLLED_BATCH_MISSING" } });
      state.records = [
        {
          ...record,
          status: "committed",
          committed_by_user_id: "controlled-user",
          committed_at: "2026-10-10T00:01:00Z",
        },
      ];
      return route.fulfill({ json: state.records[0] });
    }
    if (path === `/api/v1/governance/publication-batches/${batchId}` && request.method() === "GET")
      return state.batchDenied
        ? route.fulfill({ status: 403, json: { detail: "RAW_BATCH_DENIAL" } })
        : route.fulfill({ json: state.records[0] });
    if (path === "/api/v1/governance/projection-maintenance-access")
      return state.accessDenied
        ? route.fulfill({ status: 403, json: { detail: "RAW_GLOBAL_ACCESS_DENIAL" } })
        : route.fulfill({ json: { allowed: state.privileged } });
    if (path === "/api/v1/governance/projection-maintenance-jobs" && request.method() === "GET")
      return route.fulfill({ json: state.jobs });
    if (path === "/api/v1/governance/projection-maintenance-jobs" && request.method() === "POST") {
      const input = request.postDataJSON() as { operation: ProjectionMaintenanceJobRead["operation"] };
      if (state.holdMaintenance)
        await new Promise<void>((resolve) => {
          state.releaseMaintenance = resolve;
        });
      const job = {
        ...controlledProjectionJob,
        id: "815a81e1-5555-4444-8888-999999999999",
        operation: input.operation,
        status: "queued" as const,
        result: {},
      };
      state.jobs = [job, ...state.jobs];
      return route.fulfill({ status: 202, json: job });
    }
    return route.fulfill({ status: 403, json: { detail: "CONTROLLED_UNEXPECTED_PUBLICATION_REQUEST" } });
  });
  return state;
}
