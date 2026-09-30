import { contractRequest } from "../contract";
import type {
  DataSourceCreate,
  DataSourceDatasetRead,
  DataSourceRead,
  DataSourceReadinessRead,
  DataSourceUpdate,
  IngestionCapabilitiesRead,
  IngestionFindingRead,
  IngestionRunCancelAcceptedRead,
  IngestionRunRead,
  IngestionScanAcceptedRead,
  SearchProjectionStatusRead,
  SourceAssetDetailRead,
  SourceAssetPageRead,
  SourceVersionPreviewRead,
  SourceVersionQuarantineCaseRead,
  SourceVersionQuarantineDecisionAcceptedRead,
  SourceVersionQuarantineDecisionRequest,
  SourceVersionRead,
  SourceVersionReplayAcceptedRead,
} from "../generated";
import { DataFactoryService } from "../generated";

export const dataFactoryKeys = {
  all: ["data-factory"] as const,
  searchStatus: ["data-factory", "search-status"] as const,
  findings: (runId: string) => ["data-factory", "findings", runId] as const,
  asset: (assetId: string) => ["data-factory", "asset", assetId] as const,
  preview: (versionId: string) => ["data-factory", "preview", versionId] as const,
  quarantine: (versionId: string) => ["data-factory", "quarantine", versionId] as const,
};

export type DataFactorySnapshot = {
  capabilities: IngestionCapabilitiesRead;
  sources: DataSourceRead[];
  runs: IngestionRunRead[];
  datasets: DataSourceDatasetRead[];
  readiness: DataSourceReadinessRead[];
  quarantineCases: SourceVersionQuarantineCaseRead[];
};

export async function loadDataFactory(signal?: AbortSignal): Promise<DataFactorySnapshot> {
  const [capabilities, sources, runs, datasets, readiness, quarantineCases] = await Promise.all([
    contractRequest(DataFactoryService.getIngestionCapabilitiesApiV1AdminIngestionCapabilitiesGet(), signal),
    contractRequest(DataFactoryService.listDataSourcesApiV1AdminDataSourcesGet(), signal),
    contractRequest(DataFactoryService.listIngestionRunsApiV1AdminIngestionRunsGet({ limit: 200 }), signal),
    contractRequest(DataFactoryService.listDataSourceDatasetsApiV1AdminDataSourceDatasetsGet(), signal),
    contractRequest(DataFactoryService.listDataSourceReadinessApiV1AdminDataSourceReadinessGet(), signal),
    contractRequest(
      DataFactoryService.listSourceVersionQuarantineCasesApiV1AdminQuarantineCasesGet({ limit: 200 }),
      signal,
    ),
  ]);
  return { capabilities, sources, runs, datasets, readiness, quarantineCases };
}

export function loadSearchProjectionStatus(signal?: AbortSignal): Promise<SearchProjectionStatusRead> {
  return contractRequest(DataFactoryService.searchProjectionStatusApiV1AdminSearchStatusGet(), signal);
}

export function loadIngestionFindings(runId: string, signal?: AbortSignal): Promise<IngestionFindingRead[]> {
  return contractRequest(
    DataFactoryService.listIngestionFindingsApiV1AdminIngestionRunsRunIdFindingsGet({ runId }),
    signal,
  );
}

export function loadSourceAsset(assetId: string, signal?: AbortSignal): Promise<SourceAssetDetailRead> {
  return contractRequest(DataFactoryService.getSourceAssetDetailApiV1AdminSourceAssetsAssetIdGet({ assetId }), signal);
}

export function loadSourceAssets(offset: number, limit: number, signal?: AbortSignal): Promise<SourceAssetPageRead> {
  return contractRequest(DataFactoryService.listSourceAssetsApiV1AdminSourceAssetsGet({ offset, limit }), signal);
}

export function loadSourceVersionPreview(versionId: string, signal?: AbortSignal): Promise<SourceVersionPreviewRead> {
  return contractRequest(
    DataFactoryService.getSourceVersionPreviewApiV1AdminSourceVersionsVersionIdPreviewGet({ versionId }),
    signal,
  );
}

export function loadQuarantineCase(versionId: string, signal?: AbortSignal): Promise<SourceVersionQuarantineCaseRead> {
  return contractRequest(
    DataFactoryService.getSourceVersionQuarantineCaseApiV1AdminQuarantineCasesVersionIdGet({ versionId }),
    signal,
  );
}

export function decideQuarantineCase(
  versionId: string,
  requestBody: SourceVersionQuarantineDecisionRequest,
): Promise<SourceVersionQuarantineDecisionAcceptedRead> {
  return contractRequest(
    DataFactoryService.decideSourceVersionQuarantineCaseApiV1AdminQuarantineCasesVersionIdDecisionsPost({
      versionId,
      requestBody,
    }),
  );
}

export function replaySourceVersion(
  versionId: string,
  operationKey: string,
  expectedState: SourceVersionRead["state"],
  expectedErrorCode: string | null,
  fromStage: SourceVersionReplayAcceptedRead["from_stage"],
  reason: string,
): Promise<SourceVersionReplayAcceptedRead> {
  return contractRequest(
    DataFactoryService.replaySourceVersionApiV1AdminSourceVersionsVersionIdReplayPost({
      versionId,
      requestBody: {
        operation_key: operationKey,
        expected_state: expectedState,
        expected_error_code: expectedErrorCode,
        from_stage: fromStage,
        reason,
      },
    }),
  );
}

export function createDataSource(requestBody: DataSourceCreate): Promise<DataSourceRead> {
  return contractRequest(DataFactoryService.createDataSourceApiV1AdminDataSourcesPost({ requestBody }));
}

export function updateDataSource(dataSourceId: string, requestBody: DataSourceUpdate): Promise<DataSourceRead> {
  return contractRequest(
    DataFactoryService.updateDataSourceApiV1AdminDataSourcesDataSourceIdPatch({ dataSourceId, requestBody }),
  );
}

export function triggerDataSourceScan(dataSourceId: string): Promise<IngestionScanAcceptedRead> {
  return contractRequest(
    DataFactoryService.triggerDataSourceScanApiV1AdminDataSourcesDataSourceIdScanPost({ dataSourceId }),
  );
}

export function replayIngestionRun(
  runId: string,
  operationKey: string,
  expectedState: "failed" | "partial" | "canceled",
  reason: string,
): Promise<IngestionScanAcceptedRead> {
  return contractRequest(
    DataFactoryService.replayIngestionRunApiV1AdminIngestionRunsRunIdReplayPost({
      runId,
      requestBody: { operation_key: operationKey, expected_state: expectedState, reason },
    }),
  );
}

export function cancelIngestionRun(
  runId: string,
  operationKey: string,
  reason: string,
): Promise<IngestionRunCancelAcceptedRead> {
  return contractRequest(
    DataFactoryService.cancelIngestionRunApiV1AdminIngestionRunsRunIdCancelPost({
      runId,
      requestBody: { operation_key: operationKey, expected_state: "running", reason },
    }),
  );
}

export function updateDataSourceState(dataSourceId: string, state: "active" | "paused"): Promise<DataSourceRead> {
  return contractRequest(
    DataFactoryService.updateDataSourceStateApiV1AdminDataSourcesDataSourceIdStatePatch({
      dataSourceId,
      requestBody: { state },
    }),
  );
}

export type DataSource = DataSourceRead;
export type DataSourceDataset = DataSourceDatasetRead;
export type DataSourceReadiness = DataSourceReadinessRead;
export type IngestionCapabilities = IngestionCapabilitiesRead;
export type IngestionRun = IngestionRunRead;
export type IngestionFinding = IngestionFindingRead;
export type SearchProjectionStatus = SearchProjectionStatusRead;
export type SourceAsset = SourceAssetPageRead["items"][number];
export type SourceAssetDetail = SourceAssetDetailRead;
export type SourceVersion = SourceVersionRead;
export type SourceVersionReplayStage = SourceVersionReplayAcceptedRead["from_stage"];
export type QuarantineCase = SourceVersionQuarantineCaseRead;
export type QuarantineAction = SourceVersionQuarantineDecisionRequest["action"];
export type SourceVersionPreview = SourceVersionPreviewRead;
export type NewDataSource = DataSourceCreate;
export type DataSourcePatch = DataSourceUpdate;
