import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { ProjectionMaintenanceJob } from "../lib/contracts/governance";
import { setLocale } from "../lib/i18n";
import { ProjectionMaintenancePanel } from "../views/governance/ProjectionMaintenancePanel";

const job: ProjectionMaintenanceJob = {
  id: "controlled-job",
  operation: "consistency_check",
  status: "succeeded",
  requested_by_user_id: "controlled-user",
  attempts: 1,
  worker_id: null,
  lease_expires_at: null,
  build_id: null,
  last_error: null,
  result: { expected_counts: { entities: 12, evidence: 0 }, actual_counts: { evidence: 0 } },
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
  started_at: null,
  completed_at: null,
};
it("does not replace absent projection observations with a fabricated zero", () => {
  setLocale("en");
  render(
    <ProjectionMaintenancePanel
      jobs={[job]}
      loading={false}
      error=""
      busy={false}
      onRequest={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );
  expect(screen.getByText("Not reported / 12")).toBeInTheDocument();
  expect(screen.getByText("0 / 0")).toBeInTheDocument();
  expect(screen.queryByText("0 / 12")).not.toBeInTheDocument();
});
it("does not describe a still-loading maintenance history as empty", () => {
  render(
    <ProjectionMaintenancePanel jobs={[]} loading error="" busy={false} onRequest={vi.fn()} onRefresh={vi.fn()} />,
  );
  expect(screen.queryByText("尚无投影维护任务。")).not.toBeInTheDocument();
});
it("prevents another maintenance request when any returned job is still active", () => {
  render(
    <ProjectionMaintenancePanel
      jobs={[job, { ...job, id: "older-active", status: "running" }]}
      loading={false}
      error=""
      busy={false}
      onRequest={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "一致性检查" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "原子重建全局投影" })).toBeDisabled();
});
