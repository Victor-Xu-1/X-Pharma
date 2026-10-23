import type { DataSource, DataSourceDataset } from "../../lib/contracts/dataFactory";
import type { DataSourceCreate, DataSourceUpdate } from "../../lib/generated";
import { SourceDraftValidationError } from "./sourceDraftValidation";
import {
  initialPublicSourceDraft,
  isPublicResearchSource,
  type PublicSourceDraft,
  sourceRequiresCredential,
  sourceRoutingRules,
  toLocalDateTimeInput,
} from "./sourceRules";

export type SourceEditorDraft = {
  sourceType: DataSource["source_type"];
  name: string;
  rootUri: string;
  credentialRef: string;
  owner: string;
  authorizationScopes: string;
  authorizationValidFrom: string;
  authorizationValidUntil: string;
  classification: "public" | "internal" | "confidential" | "restricted";
  datasetKey: string;
  interval: number;
  freshness: number;
  routing: PublicSourceDraft;
};

export function initialSourceEditorDraft(
  source: DataSource | undefined,
  datasets: readonly DataSourceDataset[],
  roots: readonly string[],
): SourceEditorDraft {
  return {
    sourceType: source?.source_type ?? "folder",
    name: source?.name ?? "",
    rootUri: source?.root_uri ?? roots[0] ?? "/sources/knowledge",
    credentialRef: "",
    owner: source?.owner ?? "",
    authorizationScopes: source?.authorization_scopes.join("\n") ?? "",
    authorizationValidFrom: source
      ? toLocalDateTimeInput(source.authorization_valid_from ?? null)
      : toLocalDateTimeInput(),
    authorizationValidUntil: source?.authorization_valid_until
      ? toLocalDateTimeInput(source.authorization_valid_until)
      : "",
    classification: source?.data_classification ?? "internal",
    datasetKey: source?.dataset_key ?? datasets[0]?.dataset_key ?? "",
    interval: source?.scan_interval_seconds ?? 300,
    freshness: source?.expected_freshness_seconds ?? 86400,
    routing: initialPublicSourceDraft(source),
  };
}

export function sourceAuthorizationScopes(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((scope) => scope.trim())
    .filter(Boolean);
}

/** Retain unedited authorization timestamp precision, instead of truncating it to the minute input. */
function authorizationTimes(draft: SourceEditorDraft, source?: DataSource) {
  const from =
    source && draft.authorizationValidFrom === toLocalDateTimeInput(source.authorization_valid_from ?? null)
      ? source.authorization_valid_from
      : new Date(draft.authorizationValidFrom).toISOString();
  const until = !draft.authorizationValidUntil
    ? null
    : source?.authorization_valid_until &&
        draft.authorizationValidUntil === toLocalDateTimeInput(source.authorization_valid_until)
      ? source.authorization_valid_until
      : new Date(draft.authorizationValidUntil).toISOString();
  return { from, until };
}

export function sourceEditorPayload(
  draft: SourceEditorDraft,
  source?: DataSource,
): DataSourceCreate | DataSourceUpdate {
  const start = new Date(draft.authorizationValidFrom),
    end = draft.authorizationValidUntil ? new Date(draft.authorizationValidUntil) : null;
  if (Number.isNaN(start.getTime())) throw new SourceDraftValidationError("授权生效时间无效");
  if (end && Number.isNaN(end.getTime())) throw new SourceDraftValidationError("授权结束时间必须晚于生效时间");
  const { from, until } = authorizationTimes(draft, source);
  if (until && new Date(until) <= new Date(from)) throw new SourceDraftValidationError("授权结束时间必须晚于生效时间");
  const routing = sourceRoutingRules(draft.sourceType, draft.routing);
  const governance = {
    name: draft.name.trim(),
    owner: draft.owner.trim(),
    data_classification: draft.classification,
    authorization_scopes: sourceAuthorizationScopes(draft.authorizationScopes),
    authorization_valid_from: from,
    authorization_valid_until: until,
    scan_interval_seconds: draft.interval,
    expected_freshness_seconds: draft.freshness,
    ...(isPublicResearchSource(draft.sourceType) ? { routing_rules: routing } : {}),
    ...(sourceRequiresCredential(draft.sourceType) && draft.credentialRef.trim()
      ? { credential_ref: draft.credentialRef.trim() }
      : {}),
  };
  if (source) return governance;
  return {
    ...governance,
    source_type: draft.sourceType,
    root_uri: draft.rootUri.trim(),
    dataset_key: draft.datasetKey,
    include_globs: ["*", "**/*"],
    exclude_globs: [],
    stable_seconds: draft.sourceType === "folder" ? 30 : 0,
    max_file_bytes: 1073741824,
    rate_limit_per_minute: 60,
  };
}
