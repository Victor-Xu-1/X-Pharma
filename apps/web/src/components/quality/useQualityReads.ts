import { useQuery } from "@tanstack/react-query";
import {
  governanceKeys,
  loadDataQualityCoverage,
  loadDataQualityIssueEvents,
  loadDataQualityIssues,
  loadDataQualityOwners,
  loadDataQualitySnapshots,
} from "../../lib/contracts/governance";
import { governanceReadDenied } from "../../views/governance/governanceQueryState";

/** One query owner per quality resource. A current denial invalidates cached display authority. */
export function useQualityReads(status: string, selectedId: string) {
  const snapshots = useQuery({
    queryKey: governanceKeys.qualitySnapshots,
    queryFn: ({ signal }) => loadDataQualitySnapshots(signal),
  });
  const coverage = useQuery({
    queryKey: governanceKeys.qualityCoverage,
    queryFn: ({ signal }) => loadDataQualityCoverage(signal),
  });
  const issues = useQuery({
    queryKey: governanceKeys.qualityIssues(status),
    queryFn: ({ signal }) => loadDataQualityIssues(status, signal),
  });
  const owners = useQuery({
    queryKey: governanceKeys.qualityOwners,
    queryFn: ({ signal }) => loadDataQualityOwners(signal),
  });
  const issueData = governanceReadDenied(issues.error) ? undefined : issues.data;
  const selectedIssue = issueData?.find((issue) => issue.id === selectedId) ?? issueData?.[0] ?? null;
  const issueId = selectedIssue?.id ?? "";
  const events = useQuery({
    queryKey: governanceKeys.qualityIssueEvents(issueId || "none"),
    queryFn: ({ signal }) => loadDataQualityIssueEvents(issueId, signal),
    enabled: Boolean(issueId),
  });
  return {
    snapshots,
    coverage,
    issues,
    owners,
    events,
    selectedIssue,
    issueData,
    snapshotData: governanceReadDenied(snapshots.error) ? undefined : snapshots.data,
    coverageData: governanceReadDenied(coverage.error) ? undefined : coverage.data,
    ownerData: governanceReadDenied(owners.error) ? undefined : owners.data,
    eventData: governanceReadDenied(events.error) ? undefined : events.data,
  };
}
export function qualityReadCurrent(query: { isSuccess: boolean; isFetching: boolean; error: unknown }) {
  return query.isSuccess && !query.isFetching && !query.error;
}
export type QualityReads = ReturnType<typeof useQualityReads>;
