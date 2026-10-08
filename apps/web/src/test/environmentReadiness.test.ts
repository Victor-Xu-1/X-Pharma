import { expect, it } from "vitest";
import { environmentReadiness, probeReadiness } from "../lib/environmentReadiness";
import type { EnvironmentProbeRead, EnvironmentRead } from "../lib/generated";
import { PRODUCT_VERSION } from "../lib/product";

const probe: EnvironmentProbeRead = {
  id: "project-python",
  label: "项目 Python",
  scope: "host",
  status: "present",
  observed: "3.13.14",
  expected: ">=3.13,<3.14",
  detail: "符合声明",
};
const environment: EnvironmentRead = {
  generated_at: "2026-10-07T00:00:00Z",
  product_version: PRODUCT_VERSION,
  environment: "development",
  host_status: "current",
  host_detail: "报告有效",
  recipes: [],
  runtime: [probe],
  host: {
    generated_at: "2026-10-07T00:00:00Z",
    product_version: PRODUCT_VERSION,
    revision: "a".repeat(40),
    clean_source: true,
    manifest_sha256: "b".repeat(64),
    probes: [probe],
    disk_free_bytes: 4 * 1024 ** 3,
    disk_total_bytes: 8 * 1024 ** 3,
  },
};

it("reports only declared, observed compatible dependencies as ready", () => {
  expect(probeReadiness([probe])).toBe("ready");
  expect(environmentReadiness(environment).overall).toBe("ready");
});

it.each(["missing", "mismatch", "blocked"] as const)("retains actionable %s issues", (status) => {
  const result = environmentReadiness({ ...environment, runtime: [{ ...probe, status }] });
  expect(result.overall).toBe("repair");
  expect(result.issues).toHaveLength(1);
});

it("does not call empty, undeclared or unobserved probe sets compatible", () => {
  for (const probes of [[], [{ ...probe, expected: null }], [{ ...probe, observed: null }]]) {
    expect(probeReadiness(probes)).toBe("unverified");
  }
  expect(probeReadiness([{ ...probe, status: "unverified" }])).toBe("unverified");
});

it("does not reuse stale or missing host evidence as current readiness", () => {
  expect(environmentReadiness({ ...environment, host_status: "stale" }).overall).toBe("unverified");
  expect(environmentReadiness({ ...environment, host_status: "not_configured", host: null }).overall).toBe(
    "unverified",
  );
});

it("does not call a dirty or empty reported project ready", () => {
  const host = environment.host;
  if (!host) throw new Error("host fixture is required");
  expect(environmentReadiness({ ...environment, host: { ...host, clean_source: false } }).overall).toBe("unverified");
  expect(environmentReadiness({ ...environment, host: { ...host, probes: [] } }).overall).toBe("unverified");
});
