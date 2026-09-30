/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CommercialUsageSummaryRead = {
  active_reservations: number;
  as_of: string;
  available_units: string;
  charged_units: string;
  client_id: string;
  consumed_units: string;
  currency: string;
  granted_units: string;
  latest_statement_id: (string | null);
  latest_statement_period_end: (string | null);
  period_start: string;
  rate_card_key: string;
  rate_card_revision: number;
  reserved_units: string;
  response_bytes: number;
  result_count: number;
  settlement_count: number;
  subscription_id: string;
};
