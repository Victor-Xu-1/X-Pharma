/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuarantineStatus } from './QuarantineStatus';
import type { SourceVersionState } from './SourceVersionState';
import type { StageStatus } from './StageStatus';
export type SourceVersionRead = {
  content_sha256: string;
  discovered_at: string;
  error_code: (string | null);
  error_message: (string | null);
  extracted_text_sha256: (string | null);
  governance_status: StageStatus;
  id: string;
  malware_scan_status: StageStatus;
  malware_scanned_at: (string | null);
  malware_scanner: (string | null);
  malware_signature_version: (string | null);
  metadata_json: Record<string, any>;
  parse_status: StageStatus;
  parser_name: (string | null);
  parser_version: (string | null);
  quarantine_status: QuarantineStatus;
  quarantine_updated_at: (string | null);
  quarantine_version: number;
  replayable_stages?: Array<'malware_scan' | 'parse' | 'governance' | 'retrieval'>;
  retrieval_status: StageStatus;
  size_bytes: number;
  snapshot_status: StageStatus;
  source_asset_id: string;
  source_modified_at: (string | null);
  state: SourceVersionState;
  version_number: number;
};
