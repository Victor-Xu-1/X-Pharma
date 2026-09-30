/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewsEventLinkedEntityRead } from './NewsEventLinkedEntityRead';
export type NewsEventSearchItemRead = {
  canonical_url: (string | null);
  details: Record<string, any>;
  event_identifier: string;
  event_type: string;
  id: string;
  language: (string | null);
  published_at: (string | null);
  publisher_entity: (NewsEventLinkedEntityRead | null);
  publisher_entity_id: (string | null);
  related_entities: Array<NewsEventLinkedEntityRead>;
  related_entity_ids: Array<string>;
  source_document_id: (string | null);
  summary: (string | null);
  title: string;
  venue: (string | null);
};
