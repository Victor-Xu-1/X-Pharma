/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SearchProjectionStatusRead = {
  aliases: Record<string, Array<string>>;
  available: boolean;
  cluster_name: (string | null);
  cluster_status: (string | null);
  deliveries: Record<string, number>;
  error?: (string | null);
  version: (string | null);
};
