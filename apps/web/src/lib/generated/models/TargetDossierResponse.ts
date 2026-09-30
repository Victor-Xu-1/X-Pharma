/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BioactivityRead } from './BioactivityRead';
import type { ClinicalTrialSearchItemRead } from './ClinicalTrialSearchItemRead';
import type { CompetitiveProgramRead } from './CompetitiveProgramRead';
import type { CompoundStructureRead } from './CompoundStructureRead';
import type { DealSearchItemRead } from './DealSearchItemRead';
import type { EntityDossierCoverageRead } from './EntityDossierCoverageRead';
import type { EntityRead } from './EntityRead';
import type { EntityRelationshipRead } from './EntityRelationshipRead';
import type { NewsEventSearchItemRead } from './NewsEventSearchItemRead';
import type { PatentFamilyRead } from './PatentFamilyRead';
import type { RegulatoryEventSearchItemRead } from './RegulatoryEventSearchItemRead';
import type { TargetDossierSummaryRead } from './TargetDossierSummaryRead';
import type { TargetEvidenceRead } from './TargetEvidenceRead';
import type { TargetProfileResponse } from './TargetProfileResponse';
export type TargetDossierResponse = {
  activities: Array<BioactivityRead>;
  as_of: string;
  clinical_trials: Array<ClinicalTrialSearchItemRead>;
  coverage: Array<EntityDossierCoverageRead>;
  deals: Array<DealSearchItemRead>;
  entity: EntityRead;
  news_events: Array<NewsEventSearchItemRead>;
  patents: Array<PatentFamilyRead>;
  profile: TargetProfileResponse;
  programs: Array<CompetitiveProgramRead>;
  regulatory_events: Array<RegulatoryEventSearchItemRead>;
  relationships: Array<EntityRelationshipRead>;
  structures: Array<CompoundStructureRead>;
  summary: TargetDossierSummaryRead;
  target_evidence: Array<TargetEvidenceRead>;
  warnings?: Array<string>;
};
