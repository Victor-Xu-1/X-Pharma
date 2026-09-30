/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ProgramOrganizationRead = {
  country_region?: (string | null);
  entity_id: string;
  name: string;
  organization_type?: (string | null);
  position: number;
  role: 'originator' | 'collaborator' | 'licensee' | 'licensor' | 'manufacturer' | 'other';
};
