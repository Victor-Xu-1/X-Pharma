/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialClientSubjectRead } from './CommercialClientSubjectRead';
export type CommercialClientRead = {
  active: boolean;
  active_reservations: number;
  available_units: (string | null);
  billing_account_key: (string | null);
  client_key: string;
  created_at: string;
  denial_count_24h: number;
  display_name: string;
  id: string;
  last_policy_event_at: (string | null);
  subjects: Array<CommercialClientSubjectRead>;
  subscription_key: (string | null);
  subscription_status: (string | null);
};
