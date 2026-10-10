import type { Page } from "@playwright/test";
import type { DataRetentionPolicyRead, SourceAssetImpactRead } from "../src/lib/generated";
import { installCommercialFixture } from "./commercial-fixture";
export const controlledRetentionPolicy: DataRetentionPolicyRead = {
  id: "controlled-retention-policy",
  data_class: "commercial_export_artifact",
  policy_version: 2,
  retention_seconds: 86400,
  legal_basis: "Original legal basis <source>",
  geographic_scope: ["CN"],
  active: false,
  configured_by_user_id: "controlled-admin",
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
export const controlledSourceAsset: SourceAssetImpactRead = {
  id: "controlled-source-asset",
  data_source_id: "controlled-source",
  logical_path: "literature/original <source>.md",
  file_name: "original <source>.md",
  state: "missing",
  missing_since: "2026-09-01T00:00:00Z",
  retention_eligible: true,
  version_count: 2,
  raw_object_count: 2,
  extracted_object_count: 2,
  extraction_run_count: 1,
  staged_fact_count: 0,
  published_fact_count: 0,
  evidence_claim_count: 0,
  knowledge_citation_count: 0,
  retrieval_projection_count: 1,
  shared_document_count: 0,
  other_document_reference_count: 0,
  blockers: [],
};
/** Only controlled browser responses, never a real retention, hold or purge write. */
export async function installCommercialLifecycleFixture(page: Page) {
  const base = await installCommercialFixture(page);
  const state = {
    policies: [
      controlledRetentionPolicy,
      {
        ...controlledRetentionPolicy,
        id: "controlled-source-policy",
        data_class: "source_asset_snapshot" as const,
        active: true,
      },
    ],
    sources: [controlledSourceAsset],
    reads: 0,
    writes: [] as unknown[],
    hold: false,
    release: undefined as (() => void) | undefined,
  };
  await page.route("**/api/v1/commercial/data-lifecycle/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      state.reads++;
      if (path.endsWith("/retention-policies")) return route.fulfill({ json: state.policies });
      if (path.endsWith("/source-candidates")) return route.fulfill({ json: state.sources });
      if (
        path.endsWith("/legal-holds") ||
        path.endsWith("/events") ||
        path.endsWith("/source-assets/deleted") ||
        path.endsWith("/export-candidates")
      )
        return route.fulfill({ json: [] });
    }
    if (request.method() === "PUT" && path.endsWith("/retention-policies/export-artifacts")) {
      const payload = request.postDataJSON();
      state.writes.push(payload);
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      const policy = { ...state.policies[0], ...payload, policy_version: state.policies[0].policy_version + 1 };
      state.policies = [policy, ...state.policies.slice(1)];
      return route.fulfill({ json: policy });
    }
    if (request.method() === "POST" && path.endsWith("/source-assets/controlled-source-asset/purge")) {
      state.writes.push(request.postDataJSON());
      return route.fulfill({ status: 503, json: { detail: "RAW_CONTROLLED_PURGE_FAILURE" } });
    }
    throw new Error("Unexpected lifecycle fixture request: " + request.method() + " " + path);
  });
  return { base, state };
}
