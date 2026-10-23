import { type QueryKey, useQueryClient } from "@tanstack/react-query";
import {
  type EnterpriseAccessWorkspace,
  type EnterpriseApiKeyOperation,
  type EnterpriseGroup,
  type EnterpriseLLMProvider,
  type EnterpriseLLMProviderOperation,
  type EnterpriseOperation,
  type EnterpriseUser,
  enterpriseKeys,
} from "../../lib/contracts/enterprise";
import type { EnterpriseMessageKey } from "../../lib/i18n/enterpriseWorkspace";
import type { EnterpriseOperationBoundary } from "./useEnterpriseOperationBoundary";

/** Checks the current cache observation without refetching or rewriting a captured intent. Server authorization remains authoritative. */
export function useEnterpriseCommands(boundary: EnterpriseOperationBoundary) {
  const client = useQueryClient();
  function current<T>(key: QueryKey, matches: (data: T) => boolean = () => true) {
    if (boundary.isLocked()) return false;
    const state = client.getQueryState(key),
      data = client.getQueryData<T>(key);
    if (state?.status !== "success" || state.error || state.fetchStatus !== "idle" || data === undefined) {
      boundary.failCurrentRead();
      return false;
    }
    if (!matches(data)) {
      boundary.failStaleTarget();
      return false;
    }
    return true;
  }
  function operationCurrent(operation: EnterpriseOperation) {
    switch (operation.kind) {
      case "create-user":
        return current<EnterpriseUser[]>(enterpriseKeys.users);
      case "update-user-role":
      case "update-user-status":
        return current<EnterpriseUser[]>(enterpriseKeys.users, (users) =>
          users.some(
            (item) =>
              item.id === operation.userId && item.token_version === operation.requestBody.expected_token_version,
          ),
        );
      case "create-group":
        return current<EnterpriseGroup[]>(enterpriseKeys.groups);
      case "update-group":
        return current<EnterpriseGroup[]>(enterpriseKeys.groups, (groups) =>
          groups.some(
            (item) => item.id === operation.groupId && item.version === operation.requestBody.expected_version,
          ),
        );
      case "update-group-members":
        return (
          current<EnterpriseGroup[]>(enterpriseKeys.groups, (groups) =>
            groups.some(
              (item) => item.id === operation.groupId && item.version === operation.requestBody.expected_version,
            ),
          ) &&
          current<EnterpriseUser[]>(
            enterpriseKeys.users,
            (users) => operation.requestBody.user_ids?.every((id) => users.some((item) => item.id === id)) ?? true,
          )
        );
      case "update-dataset":
        return current<EnterpriseAccessWorkspace>(enterpriseKeys.access, (data) =>
          data.datasets.some(
            (item) => item.id === operation.datasetId && item.version === operation.requestBody.expected_version,
          ),
        );
      case "revoke-session":
        return current<EnterpriseAccessWorkspace>(enterpriseKeys.access, (data) =>
          data.sessions.some((item) => item.id === operation.sessionId && !item.current && !item.revoked_at),
        );
      case "update-client":
        return current<EnterpriseAccessWorkspace>(enterpriseKeys.access, (data) =>
          data.clients.some((item) => item.id === operation.clientId),
        );
    }
  }
  return {
    runOperation: async (key: string, operation: EnterpriseOperation, fallback: EnterpriseMessageKey) =>
      operationCurrent(operation) ? boundary.runOperation(key, operation, fallback) : false,
    runApiKeyOperation: async (key: string, operation: EnterpriseApiKeyOperation, fallback: EnterpriseMessageKey) =>
      current<EnterpriseAccessWorkspace>(
        enterpriseKeys.access,
        (data) =>
          operation.kind === "create-api-key" ||
          data.apiKeyCatalog.items.some(
            (item) => item.id === operation.keyId && item.active && item.status === "active",
          ),
      )
        ? boundary.runApiKeyOperation(key, operation, fallback)
        : null,
    runLlmOperation: async (key: string, operation: EnterpriseLLMProviderOperation, fallback: EnterpriseMessageKey) =>
      current<EnterpriseLLMProvider[]>(
        enterpriseKeys.models,
        (providers) =>
          operation.kind === "create-llm-provider" ||
          providers.some(
            (item) =>
              item.id === operation.providerId &&
              (operation.kind === "test-llm-provider" || item.version === operation.requestBody.expected_version),
          ),
      )
        ? boundary.runLlmOperation(key, operation, fallback)
        : false,
  };
}
