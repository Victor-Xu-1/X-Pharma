/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GovernanceFactOriginRead } from './GovernanceFactOriginRead';
import type { StagedFactRead } from './StagedFactRead';
export type GovernanceFactComparisonItemRead = {
  fact: StagedFactRead;
  origin: (GovernanceFactOriginRead | null);
};
