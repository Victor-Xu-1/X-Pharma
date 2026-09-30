/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GovernanceRunRead } from './GovernanceRunRead';
export type GovernanceRunPageRead = {
  current_policy_sha256: string;
  items: Array<GovernanceRunRead>;
  limit: number;
  offset: number;
  total: number;
};
