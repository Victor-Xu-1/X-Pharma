/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RegistrationRequest = {
  display_name: string;
  email: string;
  invitation_code?: (string | null);
  password: string;
  workbench: 'research' | 'internal';
};
