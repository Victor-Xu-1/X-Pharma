import { ApiError } from "../api";
import { contractRequest } from "../contract";
import { type ExportFormat, exportPayloadToBlob } from "../download";
import type {
  ComparisonSetCatalogRead,
  ComparisonSetCreate,
  ComparisonSetDetailRead,
  ComparisonSetMemberCreate,
  ComparisonSetMemberRemove,
  ComparisonSetSummaryRead,
  ComparisonSetUpdate,
  ComparisonSetVersionRead,
  EntityRead,
  SearchResult,
  WorkspaceExportCreate,
  WorkspaceExportPolicyRead,
  WorkspaceExportPolicyUpsert,
} from "../generated";
import { ComparisonSetsService, EntitiesService, WorkspaceExportsService } from "../generated";

export type CollectionPolicy = Omit<WorkspaceExportPolicyRead, "allowed_formats"> & {
  allowed_formats: ExportFormat[];
};

function normalizeExportPolicy(policy: WorkspaceExportPolicyRead): CollectionPolicy {
  const allowed = new Set<ExportFormat>(["csv", "json", "xlsx"]);
  if (!policy.allowed_formats.length || policy.allowed_formats.some((format) => !allowed.has(format as ExportFormat))) {
    throw new Error("导出策略包含不支持的文件格式");
  }
  return { ...policy, allowed_formats: policy.allowed_formats as ExportFormat[] };
}

export const collectionsKeys = {
  all: ["collections"] as const,
  catalogs: ["collections", "catalog"] as const,
  catalog: (query: string, offset: number, editableOnly = false) =>
    ["collections", "catalog", query.trim(), offset, editableOnly] as const,
  versions: (id: string) => ["collections", "versions", id] as const,
  detail: (comparisonSetId: string) => ["collections", "sets", comparisonSetId] as const,
  policy: ["collections", "export-policy"] as const,
  search: (query: string) => ["collections", "entity-search", query.trim()] as const,
};

export function loadCollectionCatalog(
  query: string,
  offset: number,
  signal?: AbortSignal,
  editableOnly = false,
): Promise<ComparisonSetCatalogRead> {
  return contractRequest(
    ComparisonSetsService.comparisonSetCatalogApiV1ComparisonSetsCatalogGet({
      q: query.trim(),
      limit: 25,
      offset,
      editableOnly,
    }),
    signal,
  );
}

export function listCollectionVersions(
  id: string,
  beforeVersion?: number,
  signal?: AbortSignal,
): Promise<ComparisonSetVersionRead[]> {
  return contractRequest(
    ComparisonSetsService.listComparisonSetVersionsApiV1ComparisonSetsComparisonSetIdVersionsGet({
      comparisonSetId: id,
      limit: 11,
      beforeVersion,
    }),
    signal,
  );
}

export function getComparisonSet(comparisonSetId: string, signal?: AbortSignal): Promise<ComparisonSetDetailRead> {
  return contractRequest(
    ComparisonSetsService.getComparisonSetApiV1ComparisonSetsComparisonSetIdGet({ comparisonSetId }),
    signal,
  );
}

export async function getWorkspaceExportPolicy(signal?: AbortSignal): Promise<CollectionPolicy | null> {
  try {
    const policy = await contractRequest(
      WorkspaceExportsService.getWorkspaceExportPolicyApiV1WorkspaceExportPolicyGet(),
      signal,
    );
    return normalizeExportPolicy(policy);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function searchCollectionEntities(query: string, signal?: AbortSignal): Promise<SearchResult> {
  return contractRequest(
    EntitiesService.searchEntitiesApiV1EntitiesGet({ q: query.trim(), limit: 25, offset: 0 }),
    signal,
  );
}

export function createComparisonSet(requestBody: ComparisonSetCreate): Promise<ComparisonSetDetailRead> {
  return contractRequest(ComparisonSetsService.createComparisonSetApiV1ComparisonSetsPost({ requestBody }));
}

export function updateComparisonSet(
  comparisonSetId: string,
  requestBody: ComparisonSetUpdate,
): Promise<ComparisonSetDetailRead> {
  return contractRequest(
    ComparisonSetsService.updateComparisonSetApiV1ComparisonSetsComparisonSetIdPatch({
      comparisonSetId,
      requestBody,
    }),
  );
}

export function addComparisonSetMember(
  comparisonSetId: string,
  requestBody: ComparisonSetMemberCreate,
): Promise<ComparisonSetDetailRead> {
  return contractRequest(
    ComparisonSetsService.addComparisonSetMemberApiV1ComparisonSetsComparisonSetIdMembersPost({
      comparisonSetId,
      requestBody,
    }),
  );
}

export function addComparisonSetMembers(
  comparisonSetId: string,
  requestBody: { entity_ids: string[]; expected_version: number },
): Promise<ComparisonSetDetailRead> {
  return contractRequest(
    ComparisonSetsService.addComparisonSetMembersApiV1ComparisonSetsComparisonSetIdMembersBatchPost({
      comparisonSetId,
      requestBody,
    }),
  );
}

export function removeComparisonSetMember(
  comparisonSetId: string,
  entityId: string,
  requestBody: ComparisonSetMemberRemove,
): Promise<ComparisonSetDetailRead> {
  return contractRequest(
    ComparisonSetsService.removeComparisonSetMemberApiV1ComparisonSetsComparisonSetIdMembersEntityIdRemovePost({
      comparisonSetId,
      entityId,
      requestBody,
    }),
  );
}

export function saveWorkspaceExportPolicy(requestBody: WorkspaceExportPolicyUpsert): Promise<CollectionPolicy> {
  return contractRequest(
    WorkspaceExportsService.configureWorkspaceExportPolicyApiV1AdminWorkspaceExportPolicyPost({ requestBody }),
  ).then(normalizeExportPolicy);
}

export async function exportComparisonSet(comparisonSetId: string, requestBody: WorkspaceExportCreate): Promise<Blob> {
  const payload = await contractRequest(
    WorkspaceExportsService.exportComparisonSetApiV1ComparisonSetsComparisonSetIdExportPost({
      comparisonSetId,
      requestBody,
    }),
  );
  return exportPayloadToBlob(payload, requestBody.export_format as ExportFormat);
}

export type CollectionDetail = ComparisonSetDetailRead;
export type CollectionEntity = EntityRead;
export type CollectionPolicyDraft = WorkspaceExportPolicyUpsert;
export type CollectionSummary = ComparisonSetSummaryRead;
