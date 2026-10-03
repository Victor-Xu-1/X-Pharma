import type {
  EnterpriseApiKey,
  EnterpriseClient,
  EnterpriseDataset,
  EnterpriseGroup,
  EnterpriseLLMProvider,
  EnterpriseSession,
  EnterpriseUser,
} from "../../lib/contracts/enterprise";

export type EnterpriseTab = "overview" | "users" | "groups" | "access" | "models" | "audit" | "invites";

export type UserAction = { user: EnterpriseUser; kind: "role" | "status" };

export type GroupAction = { group: EnterpriseGroup; kind: "edit" | "members" };

export type AccessAction =
  | { kind: "dataset"; dataset: EnterpriseDataset }
  | { kind: "session"; session: EnterpriseSession }
  | { kind: "client"; client: EnterpriseClient };

export type ApiKeyAction = { kind: "create" } | { kind: "rotate" | "revoke"; apiKey: EnterpriseApiKey };

export type LLMAction = { kind: "create" } | { kind: "edit" | "primary"; provider: EnterpriseLLMProvider };

export type LLMProviderPreset = "mimo" | "glm";
