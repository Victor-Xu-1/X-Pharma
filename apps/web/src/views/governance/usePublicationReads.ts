import { useQuery } from "@tanstack/react-query";
import {
  governanceKeys,
  loadProjectionMaintenanceAccess,
  loadProjectionMaintenanceJobs,
  loadPublicationBatch,
  loadPublicationBatches,
} from "../../lib/contracts/governance";
import { governancePublicationText as t } from "../../lib/i18n/governancePublication";
import { governanceReadDenied } from "./governanceQueryState";

export function usePublicationReads(activeBatchId: string) {
  const batches = useQuery({
    queryKey: governanceKeys.publicationBatches,
    queryFn: ({ signal }) => loadPublicationBatches(signal),
  });
  const activeBatch = useQuery({
    queryKey: governanceKeys.publicationBatch(activeBatchId || "none"),
    queryFn: ({ signal }) => loadPublicationBatch(activeBatchId, signal),
    enabled: Boolean(activeBatchId),
  });
  const maintenanceAccess = useQuery({
    queryKey: governanceKeys.projectionMaintenanceAccess,
    queryFn: ({ signal }) => loadProjectionMaintenanceAccess(signal),
  });
  const allowed = maintenanceAccess.data === true && !maintenanceAccess.error;
  const maintenanceJobs = useQuery({
    queryKey: governanceKeys.projectionMaintenanceJobs,
    queryFn: ({ signal }) => loadProjectionMaintenanceJobs(signal),
    enabled: allowed,
    refetchInterval: (query) =>
      !query.state.error && query.state.data?.some((job) => job.status === "queued" || job.status === "running")
        ? 3000
        : false,
  });
  const history = governanceReadDenied(batches.error) ? undefined : batches.data;
  const detailData = governanceReadDenied(activeBatch.error) ? undefined : activeBatch.data;
  const matches = detailData?.id === activeBatchId;
  const detail = matches ? detailData : undefined;
  const detailError =
    activeBatch.error instanceof Error
      ? activeBatch.error.message
      : detailData && !matches
        ? t("批次详情与请求标识不匹配")
        : "";
  const jobs = governanceReadDenied(maintenanceJobs.error) ? undefined : maintenanceJobs.data;
  return { batches, history, activeBatch, detail, detailError, maintenanceAccess, allowed, maintenanceJobs, jobs };
}
