/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { KnowledgePageStatus } from './KnowledgePageStatus';
export type KnowledgePageDetail = {
  compiler_version: string;
  content_json: Record<string, any>;
  content_sha256: string;
  current_version_id: (string | null);
  id: string;
  page_key: string;
  page_type: string;
  rendered_markdown: string;
  source_snapshot_at: string;
  status: KnowledgePageStatus;
  subject_entity_id: (string | null);
  title: string;
  updated_at: string;
  version_number: number;
};
