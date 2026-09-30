/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompetitiveProgramRead } from './CompetitiveProgramRead';
import type { DealSearchItemRead } from './DealSearchItemRead';
export type CompanyTimelineEventRead = {
  deal?: (DealSearchItemRead | null);
  event_type: 'program_status' | 'deal_announced';
  id: string;
  occurred_at: string;
  program?: (CompetitiveProgramRead | null);
  title: string;
};
