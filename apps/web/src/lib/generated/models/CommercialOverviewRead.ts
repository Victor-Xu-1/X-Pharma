/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialSubscriptionOverviewRead } from './CommercialSubscriptionOverviewRead';
export type CommercialOverviewRead = {
  active_client_count?: number;
  as_of: string;
  dead_billing_delivery_count?: number;
  open_dispute_count?: number;
  open_risk_count: number;
  pending_export_count?: number;
  period_start: string;
  subscriptions: Array<CommercialSubscriptionOverviewRead>;
};
