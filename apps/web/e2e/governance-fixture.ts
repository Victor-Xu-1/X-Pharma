import type { Page } from "@playwright/test";
import type {
  EntityResolutionCaseRead,
  EntityResolutionImpactRead,
  GovernanceFactComparisonRead,
  StagedFactRead,
} from "../src/lib/generated";

export const governanceFact: StagedFactRead = {
  id: "815a81e1-5555-4444-8888-111111111111",
  fact_kind: "program",
  fact_key: "controlled-program-a",
  raw_payload: { drug: { name: "原始药物 A" }, phase: "phase_2" },
  payload: { drug: { name: "原始药物 A" }, phase: "phase_2" },
  source_quote: "CONTROLLED_SOURCE_QUOTE <EGFR> 原始引文",
  source_locator: "page 3",
  source_document_id: "815a81e1-5555-4444-8888-222222222222",
  normalization_version: null,
  confidence: 0.9,
  status: "review_pending",
  quality_findings: [],
  conflict_with_ids: [],
  created_at: "2026-10-10T00:00:00Z",
};
export const secondGovernanceFact: StagedFactRead = {
  ...governanceFact,
  id: "815a81e1-5555-4444-8888-333333333333",
  fact_key: "controlled-program-b",
  raw_payload: { drug: { name: "原始药物 B" } },
  payload: { drug: { name: "原始药物 B" } },
};
export const governanceIdentity: EntityResolutionCaseRead = {
  id: "815a81e1-5555-4444-8888-444444444444",
  source_entity_id: "815a81e1-5555-4444-8888-555555555555",
  source_entity_name: "原始实体 ALK",
  candidate_entity_id: "815a81e1-5555-4444-8888-666666666666",
  candidate_entity_name: "原始候选 ALK kinase",
  entity_type: "target",
  score: 0.6,
  risk_tier: "high",
  reasons: [{ code: "CONTROLLED_MATCH_REASON" }],
  status: "pending",
  proposed_by: "controlled-fixture",
  reviewed_by_user_id: null,
  reviewed_at: null,
  review_notes: null,
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
export const governanceImpact: EntityResolutionImpactRead = {
  case: governanceIdentity,
  source_reference_count: 1,
  candidate_reference_count: 2,
  source_trusted_identifier_count: 0,
  candidate_trusted_identifier_count: 1,
  recommended_canonical_entity_id: governanceIdentity.candidate_entity_id,
  recommendation_reasons: ["CONTROLLED_RECOMMENDATION"],
  active_alias_entity_id: null,
  active_canonical_entity_id: null,
  rollback_available: false,
  references: [
    { domain: "controlled_domain", table: "original_table", column: "entity_id", source_count: 1, candidate_count: 2 },
  ],
  decisions: [],
};
export type GovernanceFixtureState = {
  facts: StagedFactRead[];
  reads: Record<string, number>;
  writes: string[];
  errors: string[];
  queueDenied: boolean;
  holdDecision: boolean;
  impactReads: number;
  release?: () => void;
};
/** This controlled browser fixture never submits a decision or business write to the live API. */
export async function installGovernanceFixture(page: Page, shared?: GovernanceFixtureState) {
  const state: GovernanceFixtureState = shared ?? {
    facts: [governanceFact, secondGovernanceFact],
    reads: {},
    writes: [],
    errors: [],
    queueDenied: false,
    holdDecision: false,
    impactReads: 0,
  };
  page.on("pageerror", (error) => state.errors.push(error.message));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      state.writes.push(`${request.method()} ${path}`);
      if (request.method() === "POST" && path === `/api/v1/governance/staged-facts/${governanceFact.id}/decision`) {
        if (state.holdDecision)
          await new Promise<void>((resolve) => {
            state.release = resolve;
          });
        state.facts = state.facts.filter((fact) => fact.id !== governanceFact.id);
        return route.fulfill({ json: { ...governanceFact, status: "published" } });
      }
      return route.fulfill({ status: 403, json: { detail: "CONTROLLED_WRITE_BLOCKED" } });
    }
    state.reads[path] = (state.reads[path] ?? 0) + 1;
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
    if (path === "/api/v1/governance/review-queue")
      return state.queueDenied
        ? route.fulfill({ status: 403, json: { detail: "RAW_QUEUE_DENIAL" } })
        : route.fulfill({ json: state.facts });
    if (path === "/api/v1/governance/entity-resolution-cases")
      return route.fulfill({
        json: new URL(request.url()).searchParams.get("status") === "pending" ? [governanceIdentity] : [],
      });
    if (path === `/api/v1/governance/entity-resolution-cases/${governanceIdentity.id}/impact`) {
      state.impactReads++;
      return route.fulfill({ json: { ...governanceImpact, candidate_reference_count: state.impactReads + 1 } });
    }
    if (path === "/api/v1/governance/publication-batches") return route.fulfill({ json: [] });
    if (path === "/api/v1/governance/projection-maintenance-access") return route.fulfill({ json: { allowed: false } });
    const fact = state.facts.find((candidate) => path === `/api/v1/governance/staged-facts/${candidate.id}/comparison`);
    if (fact) {
      const comparison: GovernanceFactComparisonRead = {
        fact,
        origin: null,
        conflicts: [],
        conflict_total: 0,
        unavailable_conflicts: 0,
        truncated: false,
      };
      return route.fulfill({ json: comparison });
    }
    return route.fulfill({ status: 403, json: { detail: "CONTROLLED_UNEXPECTED_READ" } });
  });
  return state;
}
