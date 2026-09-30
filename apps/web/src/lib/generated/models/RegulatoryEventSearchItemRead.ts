/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegulatoryDesignationType } from './RegulatoryDesignationType';
import type { RegulatoryEventLinkedEntityRead } from './RegulatoryEventLinkedEntityRead';
import type { RegulatoryLabelChangeType } from './RegulatoryLabelChangeType';
import type { RegulatorySafetySeverity } from './RegulatorySafetySeverity';
import type { RegulatorySafetySignalType } from './RegulatorySafetySignalType';
import type { RegulatorySafetyStatus } from './RegulatorySafetyStatus';
export type RegulatoryEventSearchItemRead = {
  affected_population: (string | null);
  agency: string;
  application_number: (string | null);
  approved_population: (string | null);
  biomarker: (string | null);
  decision_date: (string | null);
  designation_type: (RegulatoryDesignationType | null);
  details: Record<string, any>;
  dosage_form: (string | null);
  event_identifier: string;
  event_type: string;
  has_boxed_warning: (boolean | null);
  id: string;
  indication_entity: (RegulatoryEventLinkedEntityRead | null);
  indication_entity_id: (string | null);
  jurisdiction: string;
  label_change_type: (RegulatoryLabelChangeType | null);
  label_effective_at: (string | null);
  label_version: (string | null);
  line_of_therapy: (string | null);
  organization_entity: (RegulatoryEventLinkedEntityRead | null);
  organization_entity_id: (string | null);
  risk_actions: Array<string>;
  route_of_administration: (string | null);
  safety_confirmed_at: (string | null);
  safety_identified_at: (string | null);
  safety_resolved_at: (string | null);
  safety_severity: (RegulatorySafetySeverity | null);
  safety_signal_type: (RegulatorySafetySignalType | null);
  safety_status: (RegulatorySafetyStatus | null);
  safety_term: (string | null);
  source_document_id: (string | null);
  source_updated_at: (string | null);
  status: (string | null);
  subject_entity: RegulatoryEventLinkedEntityRead;
  subject_entity_id: string;
  title: string;
};
