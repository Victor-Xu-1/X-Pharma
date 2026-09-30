/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PlatformMigrationRead = {
  current_revision: (string | null);
  expected_revision: (string | null);
  status: 'current' | 'behind' | 'unknown';
};
