/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PlatformAlertRead } from './PlatformAlertRead';
import type { PlatformEventRead } from './PlatformEventRead';
import type { PlatformEvidenceRead } from './PlatformEvidenceRead';
import type { PlatformMigrationRead } from './PlatformMigrationRead';
import type { PlatformModelBudgetRead } from './PlatformModelBudgetRead';
import type { PlatformServiceRead } from './PlatformServiceRead';
import type { PlatformSloRead } from './PlatformSloRead';
import type { PlatformWorkflowRead } from './PlatformWorkflowRead';
export type PlatformOperationsRead = {
  alerts: Array<PlatformAlertRead>;
  environment: string;
  evidence: Array<PlatformEvidenceRead>;
  generated_at: string;
  migration: PlatformMigrationRead;
  model_budget: PlatformModelBudgetRead;
  queues: Record<string, any>;
  recent_events: Array<PlatformEventRead>;
  services: Array<PlatformServiceRead>;
  slos: Array<PlatformSloRead>;
  workflow: PlatformWorkflowRead;
};
