/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SourceVersionReplayAcceptedRead = {
  from_stage: 'malware_scan' | 'parse' | 'governance' | 'retrieval';
  source_version_id: string;
  status: string;
  workflow_id: string;
};
