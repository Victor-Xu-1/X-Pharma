/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnterpriseTenantRead } from './EnterpriseTenantRead';
export type EnterpriseOverviewRead = {
  active_group_count: number;
  active_source_count: number;
  active_user_count: number;
  admin_count: number;
  audit_event_count_24h: number;
  dataset_count: number;
  group_count: number;
  tenant: EnterpriseTenantRead;
  user_count: number;
};
