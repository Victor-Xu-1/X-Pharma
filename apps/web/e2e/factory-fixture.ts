import type { Page } from "@playwright/test";
import type { DataFactorySnapshot, DataSource, IngestionRun } from "../src/lib/contracts/dataFactory";
import type { SourceAssetDetailRead, SourceVersionQuarantineCaseRead, SourceVersionRead } from "../src/lib/generated";

/** Browser-only controlled records, never fed to ingestion or presented as actual coverage. */
export const factorySource: DataSource = {
  id: "controlled-source",
  name: "CONTROLLED SOURCE · 原始 EGFR",
  source_type: "folder",
  root_uri: "/sources/原始 EGFR",
  owner: "原始负责人",
  authorization_scopes: ["SOURCE_SCOPE"],
  authorization_valid_from: "2026-01-01T10:24:59.123456Z",
  authorization_valid_until: "2030-12-31T10:24:59.654321Z",
  data_classification: "internal",
  dataset_key: "literature",
  scan_interval_seconds: 300,
  expected_freshness_seconds: 86400,
  routing_rules: [],
  config_version: 1,
  consecutive_failures: 0,
  credential_configured: false,
  exclude_globs: [],
  include_globs: ["*", "**/*"],
  last_cursor_at: null,
  last_error: null,
  last_scanned_at: null,
  last_success_at: null,
  max_file_bytes: 1073741824,
  rate_limit_per_minute: 60,
  stable_seconds: 30,
  state: "active",
  unavailable_since: null,
};
export const factoryRun: IngestionRun = {
  id: "controlled-run",
  data_source_id: factorySource.id,
  workflow_id: "CONTROLLED 原始 workflow",
  state: "running",
  effective_state: "running",
  cancelable: true,
  cancel_requested_at: null,
  total_versions: 0,
  completed_versions: 0,
  counters: { discovered: 3 },
  progress_percent: 10,
  result: {},
  error_summary: null,
  stages: [{ stage: "discovery", status: "running", total_items: 3, completed_items: 0, failed_items: 0 }],
  created_at: "2026-10-01T00:00:00Z",
  started_at: null,
  heartbeat_at: null,
  completed_at: null,
  temporal_run_id: null,
  temporal_workflow_id: null,
};
export const factoryVersion: SourceVersionRead = {
  id: "controlled-version",
  source_asset_id: "controlled-asset",
  version_number: 1,
  content_sha256: "a".repeat(64),
  size_bytes: 1024,
  source_modified_at: null,
  discovered_at: "2026-01-01T00:00:00Z",
  state: "parsed",
  snapshot_status: "succeeded",
  malware_scan_status: "succeeded",
  parse_status: "succeeded",
  retrieval_status: "not_started",
  governance_status: "not_started",
  malware_scanner: "clamav",
  malware_signature_version: "Original signature",
  malware_scanned_at: null,
  quarantine_status: "not_applicable",
  quarantine_version: 0,
  quarantine_updated_at: null,
  extracted_text_sha256: "b".repeat(64),
  parser_name: "Original parser",
  parser_version: "1.2.3",
  metadata_json: {},
  error_code: null,
  error_message: null,
  replayable_stages: [],
};
export const factoryAsset: SourceAssetDetailRead = {
  id: "controlled-asset",
  data_source_id: factorySource.id,
  logical_path: "原始文件.pdf",
  source_uri: "file:///sources/original.pdf",
  file_name: "原始文件.pdf",
  extension: ".pdf",
  media_type: "application/pdf",
  state: "active",
  processing_mode: "parse",
  current_version_id: factoryVersion.id,
  first_seen_at: "2026-01-01T00:00:00Z",
  last_seen_at: "2026-01-01T00:00:00Z",
  missing_since: null,
  versions: [factoryVersion],
};
export const factoryQuarantine: SourceVersionQuarantineCaseRead = {
  source_version_id: "controlled-quarantine",
  source_asset_id: factoryAsset.id,
  file_name: "原始隔离文件.pdf",
  logical_path: "原始隔离文件.pdf",
  quarantine_status: "pending_review",
  quarantine_version: 1,
  updated_at: "2026-01-01T00:00:00Z",
  error_code: "malware_detected",
  error_message: "RAW_MALWARE",
  threat_name: "RAW_THREAT",
  decisions: [
    {
      id: "controlled-decision",
      action: "scan_detected",
      actor_id: "Original actor",
      actor_type: "system",
      details: {},
      expected_version: 0,
      previous_status: "not_applicable",
      source_version_id: "controlled-quarantine",
      workflow_id: null,
      reason: "原始扫描诊断 <Source>",
      resulting_version: 1,
      resulting_status: "pending_review",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
};
const snapshot: DataFactorySnapshot = {
  capabilities: {
    automatic_scheduling_enabled: true,
    durable_workflows_enabled: true,
    isolated_parser_enabled: true,
    malware_scanning_enabled: true,
    ai_governance_enabled: false,
    deterministic_governance_enabled: true,
    ai_model_configured: false,
    ai_model: null,
    ai_auto_publish_threshold: 0.95,
    allowed_folder_roots: ["/sources"],
    parseable_extensions: [".pdf"],
    asset_only_extensions: [],
  },
  sources: [factorySource],
  runs: [factoryRun],
  datasets: [
    {
      dataset_key: "literature",
      display_name: "Original dataset",
      active: true,
      license_id: "SOURCE_LICENSE",
      license_policy_version: "v1",
      permitted_channels: ["web", "mcp"],
      license_current: true,
      attribution: "Original attribution",
    },
  ],
  readiness: [
    {
      source_id: factorySource.id,
      configuration_ready: true,
      operational_status: "ready",
      checks: [],
      connector_id: "Original connector",
      incremental: true,
      replayable: true,
      delivery_channels: ["web", "mcp"],
      cursor_present: false,
      last_cursor_at: null,
      freshness_age_seconds: null,
    },
  ],
  quarantineCases: [factoryQuarantine],
};
export type FactoryFixtureState = {
  reads: number;
  writes: string[];
  errors: string[];
  holdSource: boolean;
  release?: () => void;
  assetDenied: boolean;
};

export async function installFactoryFixture(page: Page, shared?: FactoryFixtureState) {
  const state = shared ?? { reads: 0, writes: [], errors: [], holdSource: false, assetDenied: false };
  page.on("pageerror", (error) => state.errors.push(error.message));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      state.writes.push(`${request.method()} ${path}`);
      if (request.method() === "PATCH" && path === `/api/v1/admin/data-sources/${factorySource.id}`) {
        if (state.holdSource)
          await new Promise<void>((resolve) => {
            state.release = resolve;
          });
        return route.fulfill({ json: factorySource });
      }
      return route.fulfill({ status: 403, json: { detail: "CONTROLLED_WRITE_BLOCKED" } });
    }
    state.reads++;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-user",
          tenant_id: "controlled-tenant",
          email: "controlled@example.test",
          display_name: "Controlled browser fixture",
          role: "admin",
        },
      });
    const payloads: Record<string, unknown> = {
      "/api/v1/admin/ingestion-capabilities": snapshot.capabilities,
      "/api/v1/admin/data-sources": snapshot.sources,
      "/api/v1/admin/ingestion-runs": snapshot.runs,
      "/api/v1/admin/data-source-datasets": snapshot.datasets,
      "/api/v1/admin/data-source-readiness": snapshot.readiness,
      "/api/v1/admin/quarantine-cases": snapshot.quarantineCases,
      "/api/v1/admin/search/status": {
        available: true,
        cluster_name: "Original cluster",
        cluster_status: "green",
        version: "3.6.0",
        aliases: {},
        deliveries: {},
        error: null,
      },
    };
    if (Object.hasOwn(payloads, path)) return route.fulfill({ json: payloads[path] });
    if (path === "/api/v1/admin/source-assets")
      return route.fulfill({
        json: { items: [factoryAsset], total: 1070, limit: 50, offset: Number(url.searchParams.get("offset") ?? 0) },
      });
    if (path === `/api/v1/admin/source-assets/${factoryAsset.id}`)
      return state.assetDenied
        ? route.fulfill({ status: 403, json: { detail: "RAW_ASSET_DENIAL" } })
        : route.fulfill({ json: factoryAsset });
    if (path === `/api/v1/admin/source-versions/${factoryVersion.id}/preview`)
      return route.fulfill({
        json: {
          source_version_id: factoryVersion.id,
          extracted_text_sha256: factoryVersion.extracted_text_sha256,
          text: "原始科学正文 <EGFR>",
          returned_chars: 15,
          truncated: false,
        },
      });
    if (path === `/api/v1/admin/quarantine-cases/${factoryQuarantine.source_version_id}`)
      return route.fulfill({ json: factoryQuarantine });
    if (path.endsWith("/findings")) return route.fulfill({ json: [] });
    return route.fulfill({ json: [] });
  });
  return state;
}
