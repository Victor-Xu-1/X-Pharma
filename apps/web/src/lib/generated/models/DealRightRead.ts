/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealRightType } from './DealRightType';
export type DealRightRead = {
  exclusive: (boolean | null);
  holder_entity_id: string;
  holder_name: string;
  id: string;
  right_type: DealRightType;
  scope_description: (string | null);
  source_document_id: (string | null);
  territory: string;
};
