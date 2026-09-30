/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CommercialAdjustmentRead = {
  adjustment_key: string;
  adjustment_kind: string;
  created_at: string;
  created_by: string;
  id: string;
  reason: string;
  request_id: string;
  reverses_adjustment_id: (string | null);
  reverses_settlement_id: (string | null);
  subscription_id: string;
  units_delta: string;
};
