/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GovernanceFactComparisonItemRead } from './GovernanceFactComparisonItemRead';
import type { GovernanceFactOriginRead } from './GovernanceFactOriginRead';
import type { StagedFactRead } from './StagedFactRead';
export type GovernanceFactComparisonRead = {
  conflict_total: number;
  conflicts: Array<GovernanceFactComparisonItemRead>;
  fact: StagedFactRead;
  origin: (GovernanceFactOriginRead | null);
  truncated: boolean;
  unavailable_conflicts: number;
};
