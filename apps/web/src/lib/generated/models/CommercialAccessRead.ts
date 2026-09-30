/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialEntitlementRead } from './CommercialEntitlementRead';
export type CommercialAccessRead = {
  as_of: string;
  available_units: string;
  client_id: string;
  consumed_units: string;
  entitlements: Array<CommercialEntitlementRead>;
  reserved_units: string;
  status: string;
  subscription_id: string;
};
