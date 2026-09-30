import { ApiError } from "../api";
import { contractRequest } from "../contract";
import { WorkspaceService, type WorkspaceTablePreferenceRead } from "../generated";

export const workspaceTablePreferenceKeys = [
  "clinical-trials",
  "deals",
  "entity-search",
  "epidemiology",
  "news-events",
  "patent-families",
  "pipeline",
  "regulatory-events",
] as const;

export type WorkspaceTablePreferenceKey = (typeof workspaceTablePreferenceKeys)[number];
export type WorkspaceTableDensity = "comfortable" | "compact";
export type WorkspaceTablePreferences = {
  columnOrder: string[];
  columnVisibility: Record<string, boolean>;
  density: WorkspaceTableDensity;
};
export type WorkspaceTablePreferenceSnapshot = WorkspaceTablePreferences & {
  persisted: boolean;
  preferenceKey: WorkspaceTablePreferenceKey;
  updatedAt: string | null;
  version: number;
};

const columnIdPattern = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$/;

export const workspacePreferenceKeys = {
  table: (userId: string, preferenceKey: WorkspaceTablePreferenceKey) =>
    ["workspace", "table-preference", userId, preferenceKey] as const,
};

export function defaultWorkspaceTablePreference(
  preferenceKey: WorkspaceTablePreferenceKey,
): WorkspaceTablePreferenceSnapshot {
  return {
    columnOrder: [],
    columnVisibility: {},
    density: "comfortable",
    persisted: false,
    preferenceKey,
    updatedAt: null,
    version: 0,
  };
}

function normalizeColumnOrder(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 64) throw new Error("Invalid table preference column order");
  const result = value.filter((columnId): columnId is string => {
    return typeof columnId === "string" && columnIdPattern.test(columnId);
  });
  if (result.length !== value.length || new Set(result).size !== result.length) {
    throw new Error("Invalid table preference column order");
  }
  return result;
}

function normalizeColumnVisibility(value: unknown): Record<string, boolean> {
  if (value === undefined) return {};
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Invalid table preference column visibility");
  }
  const entries = Object.entries(value);
  if (entries.length > 64) throw new Error("Invalid table preference column visibility");
  if (entries.some(([columnId, visible]) => !columnIdPattern.test(columnId) || typeof visible !== "boolean")) {
    throw new Error("Invalid table preference column visibility");
  }
  return Object.fromEntries(entries);
}

function normalizeWorkspaceTablePreference(
  preferenceKey: WorkspaceTablePreferenceKey,
  value: WorkspaceTablePreferenceRead,
): WorkspaceTablePreferenceSnapshot {
  if (
    value.preference_key !== preferenceKey ||
    (value.schema_version ?? 1) !== 1 ||
    !Number.isInteger(value.version) ||
    value.version < 0 ||
    typeof value.persisted !== "boolean"
  ) {
    throw new Error("Invalid table preference response");
  }
  if (value.density !== undefined && value.density !== "comfortable" && value.density !== "compact") {
    throw new Error("Invalid table preference density");
  }
  if (value.persisted !== value.version > 0) throw new Error("Invalid table preference version state");
  return {
    columnOrder: normalizeColumnOrder(value.column_order ?? []),
    columnVisibility: normalizeColumnVisibility(value.column_visibility),
    density: value.density === "compact" ? "compact" : "comfortable",
    persisted: value.persisted,
    preferenceKey,
    updatedAt: value.updated_at ?? null,
    version: value.version,
  };
}

export async function loadWorkspaceTablePreference(
  preferenceKey: WorkspaceTablePreferenceKey,
  signal?: AbortSignal,
): Promise<WorkspaceTablePreferenceSnapshot> {
  const response = await contractRequest(
    WorkspaceService.getWorkspaceTablePreferenceApiV1WorkspaceTablePreferencesPreferenceKeyGet({ preferenceKey }),
    signal,
  );
  return normalizeWorkspaceTablePreference(preferenceKey, response);
}

async function updateWorkspaceTablePreference(
  preferenceKey: WorkspaceTablePreferenceKey,
  preferences: WorkspaceTablePreferences,
  expectedVersion: number,
): Promise<WorkspaceTablePreferenceSnapshot> {
  const response = await contractRequest(
    WorkspaceService.updateWorkspaceTablePreferenceApiV1WorkspaceTablePreferencesPreferenceKeyPut({
      preferenceKey,
      requestBody: {
        column_order: preferences.columnOrder,
        column_visibility: preferences.columnVisibility,
        density: preferences.density,
        expected_version: expectedVersion,
        schema_version: 1,
      },
    }),
  );
  return normalizeWorkspaceTablePreference(preferenceKey, response);
}

export async function saveWorkspaceTablePreference(
  preferenceKey: WorkspaceTablePreferenceKey,
  preferences: WorkspaceTablePreferences,
  expectedVersion: number,
): Promise<WorkspaceTablePreferenceSnapshot> {
  try {
    return await updateWorkspaceTablePreference(preferenceKey, preferences, expectedVersion);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 409) throw error;
    const latest = await loadWorkspaceTablePreference(preferenceKey);
    return updateWorkspaceTablePreference(preferenceKey, preferences, latest.version);
  }
}
