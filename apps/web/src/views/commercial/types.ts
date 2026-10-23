import type {
  BillingAccount,
  BillingDelivery,
  BillingDispute,
  BillingDisputeAction,
  CommercialClient,
  CommercialOperation,
  CommercialRiskEvent,
  RiskCaseStatus,
} from "../../lib/contracts/commercial";
import type { commercialWorkspaceMessages } from "../../lib/i18n/commercialWorkspace";
export type CommercialOperationRunner = (
  key: string,
  operation: CommercialOperation,
  fallback: keyof typeof commercialWorkspaceMessages,
) => Promise<boolean>;

export type CommercialTab =
  | "overview"
  | "clients"
  | "billing"
  | "disputes"
  | "exports"
  | "export-policy"
  | "risks"
  | "lifecycle";

export type ClientAction = { client: CommercialClient; active: boolean };

export type RiskAction = { event: CommercialRiskEvent; status: Exclude<RiskCaseStatus, "open"> };

export type MappingAction = { account: BillingAccount };

export type ReplayAction = { delivery: BillingDelivery };

export type CreateDisputeAction = { delivery: BillingDelivery; disputeKey: string };

export type DisputeCaseAction = { dispute: BillingDispute; action: BillingDisputeAction; operationKey: string };
