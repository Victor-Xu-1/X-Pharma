/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ComparisonSetMemberRead } from './ComparisonSetMemberRead';
import type { SavedSearchVisibility } from './SavedSearchVisibility';
export type ComparisonSetDetailRead = {
  created_at: string;
  description: string;
  editable: boolean;
  id: string;
  member_count: number;
  members: Array<ComparisonSetMemberRead>;
  name: string;
  owner_user_id: string;
  updated_at: string;
  version: number;
  visibility: SavedSearchVisibility;
};
