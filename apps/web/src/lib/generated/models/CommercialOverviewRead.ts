/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialSubscriptionOverviewRead } from './CommercialSubscriptionOverviewRead';
export type CommercialOverviewRead = {
  as_of: string;
  open_risk_count: number;
  period_start: string;
  subscriptions: Array<CommercialSubscriptionOverviewRead>;
};
