/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SourceAssetState } from './SourceAssetState';
export type SourceAssetRead = {
  current_version_id: (string | null);
  data_source_id: string;
  extension: string;
  file_name: string;
  first_seen_at: string;
  id: string;
  last_seen_at: string;
  logical_path: string;
  media_type: (string | null);
  missing_since: (string | null);
  processing_mode: string;
  source_uri: string;
  state: SourceAssetState;
};
