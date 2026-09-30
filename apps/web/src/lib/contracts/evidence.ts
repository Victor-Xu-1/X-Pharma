import { contractRequest } from "../contract";
import type {
  EvidenceDatasetRead,
  EvidenceSearchResponse,
  EvidenceChunk as GeneratedEvidenceChunk,
} from "../generated";
import { EvidenceService } from "../generated";

export type EvidenceChunk = Omit<GeneratedEvidenceChunk, "metadata" | "positions" | "similarity"> & {
  metadata: Record<string, unknown>;
  positions: unknown[];
  similarity: number | null;
};

export type EvidenceResult = Omit<EvidenceSearchResponse, "chunks"> & { chunks: EvidenceChunk[] };

export const evidenceKeys = {
  datasets: ["evidence", "datasets"] as const,
  search: (query: string, datasetKeys: string[]) =>
    ["evidence", "search", { query, datasetKeys: [...datasetKeys].sort() }] as const,
};

export async function listEvidenceDatasets(signal?: AbortSignal): Promise<EvidenceDatasetRead[]> {
  return contractRequest(EvidenceService.listEvidenceDatasetsApiV1EvidenceDatasetsGet(), signal);
}

export async function searchEvidence({
  query,
  datasetKeys,
  signal,
}: {
  query: string;
  datasetKeys: string[];
  signal?: AbortSignal;
}): Promise<EvidenceResult> {
  const result = await contractRequest(
    EvidenceService.searchEvidenceApiV1EvidenceSearchPost({
      requestBody: { query: query.trim(), dataset_keys: datasetKeys, limit: 20 },
    }),
    signal,
  );
  return {
    ...result,
    chunks: result.chunks.map((chunk) => ({
      ...chunk,
      metadata: chunk.metadata ?? {},
      positions: chunk.positions ?? [],
      similarity: chunk.similarity ?? null,
    })),
  };
}
