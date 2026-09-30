/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnterpriseApiKeyRead } from './EnterpriseApiKeyRead';
export type EnterpriseApiKeyCatalogRead = {
  allowed_scopes: Array<string>;
  items: Array<EnterpriseApiKeyRead>;
  max_ttl_days: number;
  min_ttl_hours: number;
  required_scope: string;
};
