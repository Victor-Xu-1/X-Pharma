/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CommercialReserveRequest = {
  billing_class: string;
  idempotency_key: string;
  max_billable_units: (number | string);
  request_arguments: Record<string, any>;
  requested_compute_units?: (number | string);
  requested_result_limit: number;
};
