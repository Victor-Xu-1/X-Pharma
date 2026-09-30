/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ProgramIndicationRead = {
  china_phase?: (string | null);
  china_phase_started_at?: (string | null);
  disease_entity_id?: (string | null);
  disease_name?: (string | null);
  geography?: (string | null);
  global_phase?: (string | null);
  global_phase_started_at?: (string | null);
  phase: string;
  program_id: string;
  program_status?: ('active' | 'inactive' | 'unknown' | null);
  status_date?: (string | null);
};
