/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PatentClaimRead } from './PatentClaimRead';
import type { PatentLegalEventRead } from './PatentLegalEventRead';
import type { PatentPublicationRead } from './PatentPublicationRead';
export type PatentFamilyRead = {
  applicants: Array<string>;
  entity_id: string;
  expiration_date: (string | null);
  family_identifier: string;
  id: string;
  independent_claims?: Array<PatentClaimRead>;
  inventors: Array<string>;
  legal_events?: Array<PatentLegalEventRead>;
  legal_status: (string | null);
  legal_status_at: (string | null);
  linked_entity_ids: Array<string>;
  priority_date: (string | null);
  publications: Array<PatentPublicationRead>;
  source_document_id: (string | null);
  title: string;
};
