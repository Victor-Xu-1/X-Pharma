/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialSettlementRead } from './CommercialSettlementRead';
import type { UsageReservationState } from './UsageReservationState';
export type CommercialReservationRead = {
  billing_class: string;
  estimated_units: string;
  lease_expires_at: string;
  page_depth: number;
  replayed: boolean;
  requested_compute_units: string;
  reservation_id: string;
  reserved_units: string;
  settlement?: (CommercialSettlementRead | null);
  state: UsageReservationState;
};
