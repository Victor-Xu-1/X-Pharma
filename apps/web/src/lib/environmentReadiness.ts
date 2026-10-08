import type { EnvironmentProbeRead, EnvironmentRead } from "./generated";

export type DependencyReadiness = "ready" | "repair" | "unverified";

export function probeReadiness(probes: EnvironmentProbeRead[]): DependencyReadiness {
  if (probes.some((probe) => ["missing", "mismatch", "blocked"].includes(probe.status))) return "repair";
  if (!probes.length || probes.some((probe) => probe.status !== "present" || !probe.expected || !probe.observed)) {
    return "unverified";
  }
  return "ready";
}

export function environmentReadiness(environment: EnvironmentRead) {
  const gateway = probeReadiness(environment.runtime);
  const host =
    environment.host_status === "current" && environment.host?.clean_source
      ? probeReadiness(environment.host.probes)
      : "unverified";
  const overall: DependencyReadiness =
    gateway === "repair" || host === "repair"
      ? "repair"
      : gateway === "ready" && host === "ready"
        ? "ready"
        : "unverified";
  const issues = [
    ...environment.runtime,
    ...(environment.host_status === "current" ? (environment.host?.probes ?? []) : []),
  ].filter((probe) => ["missing", "mismatch", "blocked"].includes(probe.status));
  return { gateway, host, overall, issues };
}

export const dependencyReadinessLabels = {
  ready: "依赖可用",
  repair: "需修复或更新",
  unverified: "待核对",
} as const satisfies Record<DependencyReadiness, string>;
