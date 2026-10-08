import { readFileSync } from "node:fs";
import type { EnvironmentInstallPlanRead, EnvironmentRead, PlatformOperationsRead } from "../../src/lib/generated";

const productVersion: string = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8")).version;

/** Synthetic browser responses only, never host/production acceptance evidence. */
export function environmentLanguageFixture() {
  const at = "2026-10-09T00:00:00Z";
  const environment: EnvironmentRead = {
    generated_at: at,
    product_version: productVersion,
    environment: "controlled-browser-fixture",
    host_status: "current",
    host_detail: "原始主机诊断 — browser fixture, not host acceptance",
    runtime: [
      {
        id: "python",
        label: "Python",
        scope: "gateway",
        status: "present",
        observed: null,
        expected: ">=3.13,<3.14",
        detail: "原始探针诊断 / controlled fixture",
      },
    ],
    host: {
      generated_at: at,
      product_version: productVersion,
      revision: "a".repeat(40),
      manifest_sha256: "b".repeat(64),
      clean_source: true,
      probes: [],
      disk_free_bytes: 4 * 1024 ** 3,
      disk_total_bytes: 8 * 1024 ** 3,
    },
    recipes: [
      {
        id: "frontend-dependencies",
        label: "前端依赖",
        description: "使用项目声明的 pnpm 和冻结锁文件，不升级依赖。",
        prerequisites: ["Node.js", "Corepack"],
        offline_supported: true,
      },
      {
        id: "python-dependencies",
        label: "Python 依赖",
        description: "按 uv.lock 安装到当前项目的 .venv，不修改系统 Python。",
        prerequisites: ["uv", "Python 3.13"],
        offline_supported: true,
      },
    ],
  };
  const platform: PlatformOperationsRead = {
    generated_at: at,
    environment: environment.environment,
    queues: { ingestion: {}, outbox: { pending: 0 }, governance: {}, deliveries: { search: {} } },
    services: [],
    slos: [],
    alerts: [],
    evidence: [],
    recent_events: [],
    migration: { status: "unknown", current_revision: null, expected_revision: null },
    workflow: {
      engine: "temporal",
      enabled: false,
      namespace: "controlled-namespace",
      task_queue: "controlled-queue",
      max_concurrent_activities: 0,
    },
    model_budget: {
      window: "24h",
      provider: "disabled",
      model: "none",
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: "0",
      max_document_cost: "0",
      failed_runs: 0,
      run_count: 0,
    },
  };
  const plan: EnvironmentInstallPlanRead = {
    generated_at: at,
    expires_at: "2026-10-10T00:00:00Z",
    product_version: productVersion,
    revision: "a".repeat(40),
    manifest_sha256: "b".repeat(64),
    plan_id: "c".repeat(64),
    recipe_id: "frontend-dependencies",
    offline: true,
    commands: [["corepack", "pnpm@11.7.0", "--dir", "apps/web", "install", "--frozen-lockfile", "--offline"]],
  };
  return { environment, platform, plan };
}
