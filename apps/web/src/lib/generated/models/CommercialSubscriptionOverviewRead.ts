/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialDailyUsageRead } from './CommercialDailyUsageRead';
import type { CommercialEntitlementRead } from './CommercialEntitlementRead';
export type CommercialSubscriptionOverviewRead = {
  active_reservations: number;
  available_units: string;
  billing_account_key: string;
  billing_account_name: string;
  client_key: string;
  client_name: string;
  consumed_units: string;
  daily_unique_records: number;
  daily_usage: CommercialDailyUsageRead;
  ends_at: (string | null);
  entitlements: Array<CommercialEntitlementRead>;
  granted_units: string;
  rate_card_key: string;
  rate_card_revision: number;
  reserved_units: string;
  starts_at: string;
  status: string;
  subscription_id: string;
  subscription_key: string;
};
