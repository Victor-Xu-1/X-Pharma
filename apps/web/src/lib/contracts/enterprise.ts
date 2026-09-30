import { contractRequest } from "../contract";
import type {
  CommercialClientRead,
  CommercialClientStatusUpdate,
  DataRetentionPolicyRead,
  EnterpriseApiKeyCatalogRead,
  EnterpriseApiKeyCreate,
  EnterpriseApiKeyRead,
  EnterpriseApiKeyRevoke,
  EnterpriseApiKeyRotate,
  EnterpriseApiKeySecretRead,
  EnterpriseAuditPageRead,
  EnterpriseDatasetRead,
  EnterpriseDatasetStatusUpdate,
  EnterpriseLLMProviderCreate,
  EnterpriseLLMProviderPrimaryUpdate,
  EnterpriseLLMProviderRead,
  EnterpriseLLMProviderUpdate,
  EnterpriseOverviewRead,
  EnterpriseSessionRead,
  EnterpriseUserCreate,
  EnterpriseUserRead,
  EnterpriseUserRoleUpdate,
  EnterpriseUserStatusUpdate,
  LegalHoldRead,
  PlatformOperationsRead,
  UserGroupCreate,
  UserGroupMembershipUpdate,
  UserGroupRead,
  UserGroupUpdate,
} from "../generated";
import { CommercialService, EnterpriseService } from "../generated";

export type EnterpriseOverview = EnterpriseOverviewRead;
export type EnterpriseUser = EnterpriseUserRead;
export type EnterpriseGroup = UserGroupRead;
export type EnterpriseAuditPage = EnterpriseAuditPageRead;
export type EnterpriseDataset = EnterpriseDatasetRead;
export type EnterpriseSession = EnterpriseSessionRead;
export type EnterpriseClient = CommercialClientRead;
export type EnterpriseApiKey = EnterpriseApiKeyRead;
export type EnterpriseApiKeyCatalog = EnterpriseApiKeyCatalogRead;
export type EnterpriseApiKeySecret = EnterpriseApiKeySecretRead;
export type EnterpriseLLMProvider = EnterpriseLLMProviderRead;

export const enterpriseKeys = {
  root: ["enterprise"] as const,
  workspace: ["enterprise", "workspace"] as const,
  audit: (filters: EnterpriseAuditFilters) => ["enterprise", "audit", filters] as const,
};

export type EnterpriseWorkspace = {
  overview: EnterpriseOverview;
  users: EnterpriseUser[];
  groups: EnterpriseGroup[];
  datasets: EnterpriseDatasetRead[];
  sessions: EnterpriseSessionRead[];
  apiKeyCatalog: EnterpriseApiKeyCatalogRead;
  clients: CommercialClientRead[];
  retentionPolicies: DataRetentionPolicyRead[];
  legalHolds: LegalHoldRead[];
  platform: PlatformOperationsRead;
  llmProviders: EnterpriseLLMProviderRead[];
};

export type EnterpriseAuditFilters = {
  cursor?: string;
  action?: string;
  outcome?: string;
  actorType?: "agent" | "api_key" | "user";
};

export async function loadEnterpriseWorkspace(signal?: AbortSignal): Promise<EnterpriseWorkspace> {
  const [
    overview,
    users,
    groups,
    datasets,
    sessions,
    apiKeyCatalog,
    clients,
    retentionPolicies,
    legalHolds,
    platform,
    llmProviders,
  ] = await Promise.all([
    contractRequest(EnterpriseService.enterpriseOverviewApiV1EnterpriseOverviewGet(), signal),
    contractRequest(EnterpriseService.listEnterpriseUsersApiV1EnterpriseUsersGet(), signal),
    contractRequest(EnterpriseService.listEnterpriseGroupsApiV1EnterpriseGroupsGet(), signal),
    contractRequest(EnterpriseService.listEnterpriseDatasetsApiV1EnterpriseDatasetsGet(), signal),
    contractRequest(EnterpriseService.listEnterpriseSessionsApiV1EnterpriseSessionsGet({ limit: 200 }), signal),
    contractRequest(EnterpriseService.listEnterpriseApiKeysApiV1EnterpriseApiKeysGet({ limit: 200 }), signal),
    contractRequest(CommercialService.listCommercialClientsApiV1CommercialClientsGet({ limit: 200 }), signal),
    contractRequest(
      CommercialService.listDataRetentionPoliciesApiV1CommercialDataLifecycleRetentionPoliciesGet(),
      signal,
    ),
    contractRequest(
      CommercialService.listLegalHoldsApiV1CommercialDataLifecycleLegalHoldsGet({ activeOnly: false }),
      signal,
    ),
    contractRequest(EnterpriseService.enterprisePlatformOperationsApiV1EnterprisePlatformGet(), signal),
    contractRequest(EnterpriseService.listEnterpriseLlmProvidersApiV1EnterpriseLlmProvidersGet(), signal),
  ]);
  return {
    overview,
    users,
    groups,
    datasets,
    sessions,
    apiKeyCatalog,
    clients,
    retentionPolicies,
    legalHolds,
    platform,
    llmProviders,
  };
}

export function loadEnterpriseAudit(
  filters: EnterpriseAuditFilters,
  signal?: AbortSignal,
): Promise<EnterpriseAuditPage> {
  return contractRequest(
    EnterpriseService.listEnterpriseAuditEventsApiV1EnterpriseAuditEventsGet({
      limit: 100,
      cursor: filters.cursor,
      action: filters.action,
      outcome: filters.outcome,
      actorType: filters.actorType,
    }),
    signal,
  );
}

export type EnterpriseOperation =
  | { kind: "create-user"; requestBody: EnterpriseUserCreate }
  | { kind: "update-user-role"; userId: string; requestBody: EnterpriseUserRoleUpdate }
  | { kind: "update-user-status"; userId: string; requestBody: EnterpriseUserStatusUpdate }
  | { kind: "create-group"; requestBody: UserGroupCreate }
  | { kind: "update-group"; groupId: string; requestBody: UserGroupUpdate }
  | { kind: "update-group-members"; groupId: string; requestBody: UserGroupMembershipUpdate }
  | { kind: "update-dataset"; datasetId: string; requestBody: EnterpriseDatasetStatusUpdate }
  | { kind: "revoke-session"; sessionId: string; requestBody: { reason: string } }
  | { kind: "update-client"; clientId: string; requestBody: CommercialClientStatusUpdate };

export type EnterpriseLLMProviderOperation =
  | { kind: "create-llm-provider"; requestBody: EnterpriseLLMProviderCreate }
  | { kind: "update-llm-provider"; providerId: string; requestBody: EnterpriseLLMProviderUpdate }
  | { kind: "make-llm-primary"; providerId: string; requestBody: EnterpriseLLMProviderPrimaryUpdate }
  | { kind: "test-llm-provider"; providerId: string };

export type EnterpriseApiKeyOperation =
  | { kind: "create-api-key"; requestBody: EnterpriseApiKeyCreate }
  | { kind: "rotate-api-key"; keyId: string; requestBody: EnterpriseApiKeyRotate }
  | { kind: "revoke-api-key"; keyId: string; requestBody: EnterpriseApiKeyRevoke };

export function executeEnterpriseOperation(operation: EnterpriseOperation): Promise<unknown> {
  switch (operation.kind) {
    case "create-user":
      return contractRequest(
        EnterpriseService.createEnterpriseUserApiV1EnterpriseUsersPost({ requestBody: operation.requestBody }),
      );
    case "update-user-role":
      return contractRequest(
        EnterpriseService.updateEnterpriseUserRoleApiV1EnterpriseUsersUserIdRolePost({
          userId: operation.userId,
          requestBody: operation.requestBody,
        }),
      );
    case "update-user-status":
      return contractRequest(
        EnterpriseService.updateEnterpriseUserStatusApiV1EnterpriseUsersUserIdStatusPost({
          userId: operation.userId,
          requestBody: operation.requestBody,
        }),
      );
    case "create-group":
      return contractRequest(
        EnterpriseService.createEnterpriseGroupApiV1EnterpriseGroupsPost({ requestBody: operation.requestBody }),
      );
    case "update-group":
      return contractRequest(
        EnterpriseService.updateEnterpriseGroupApiV1EnterpriseGroupsGroupIdPut({
          groupId: operation.groupId,
          requestBody: operation.requestBody,
        }),
      );
    case "update-group-members":
      return contractRequest(
        EnterpriseService.updateEnterpriseGroupMembersApiV1EnterpriseGroupsGroupIdMembersPut({
          groupId: operation.groupId,
          requestBody: operation.requestBody,
        }),
      );
    case "update-dataset":
      return contractRequest(
        EnterpriseService.updateEnterpriseDatasetStatusApiV1EnterpriseDatasetsDatasetIdStatusPost({
          datasetId: operation.datasetId,
          requestBody: operation.requestBody,
        }),
      );
    case "revoke-session":
      return contractRequest(
        EnterpriseService.revokeEnterpriseSessionApiV1EnterpriseSessionsSessionIdRevokePost({
          sessionId: operation.sessionId,
          requestBody: operation.requestBody,
        }),
      );
    case "update-client":
      return contractRequest(
        CommercialService.updateCommercialClientStatusApiV1CommercialClientsClientIdStatusPost({
          clientId: operation.clientId,
          requestBody: operation.requestBody,
        }),
      );
  }
}

export function executeEnterpriseApiKeyOperation(
  operation: EnterpriseApiKeyOperation,
): Promise<EnterpriseApiKeyRead | EnterpriseApiKeySecretRead> {
  switch (operation.kind) {
    case "create-api-key":
      return contractRequest(
        EnterpriseService.createEnterpriseApiKeyApiV1EnterpriseApiKeysPost({ requestBody: operation.requestBody }),
      );
    case "rotate-api-key":
      return contractRequest(
        EnterpriseService.rotateEnterpriseApiKeyApiV1EnterpriseApiKeysKeyIdRotatePost({
          keyId: operation.keyId,
          requestBody: operation.requestBody,
        }),
      );
    case "revoke-api-key":
      return contractRequest(
        EnterpriseService.revokeEnterpriseApiKeyApiV1EnterpriseApiKeysKeyIdRevokePost({
          keyId: operation.keyId,
          requestBody: operation.requestBody,
        }),
      );
  }
}

export function executeEnterpriseLLMProviderOperation(
  operation: EnterpriseLLMProviderOperation,
): Promise<EnterpriseLLMProviderRead | EnterpriseLLMProviderRead[]> {
  switch (operation.kind) {
    case "create-llm-provider":
      return contractRequest(
        EnterpriseService.createEnterpriseLlmProviderApiV1EnterpriseLlmProvidersPost({
          requestBody: operation.requestBody,
        }),
      );
    case "update-llm-provider":
      return contractRequest(
        EnterpriseService.updateEnterpriseLlmProviderApiV1EnterpriseLlmProvidersProviderIdPut({
          providerId: operation.providerId,
          requestBody: operation.requestBody,
        }),
      );
    case "make-llm-primary":
      return contractRequest(
        EnterpriseService.makeEnterpriseLlmProviderPrimaryApiV1EnterpriseLlmProvidersProviderIdMakePrimaryPost({
          providerId: operation.providerId,
          requestBody: operation.requestBody,
        }),
      );
    case "test-llm-provider":
      return contractRequest(
        EnterpriseService.testEnterpriseLlmProviderApiV1EnterpriseLlmProvidersProviderIdTestPost({
          providerId: operation.providerId,
        }),
      );
  }
}
