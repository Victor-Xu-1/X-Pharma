/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemistrySavedSearchQuery } from './ChemistrySavedSearchQuery';
import type { ClinicalTrialSavedSearchQuery } from './ClinicalTrialSavedSearchQuery';
import type { DealSavedSearchQuery } from './DealSavedSearchQuery';
import type { EntitySearchQuery } from './EntitySearchQuery';
import type { EpidemiologySavedSearchQuery } from './EpidemiologySavedSearchQuery';
import type { NewsSavedSearchQuery } from './NewsSavedSearchQuery';
import type { PatentSavedSearchQuery } from './PatentSavedSearchQuery';
import type { PipelineSavedSearchQuery } from './PipelineSavedSearchQuery';
import type { RegulatorySavedSearchQuery } from './RegulatorySavedSearchQuery';
import type { SavedSearchVisibility } from './SavedSearchVisibility';
export type SavedSearchUpdate = {
  description?: (string | null);
  name?: (string | null);
  query?: (EntitySearchQuery | ChemistrySavedSearchQuery | PipelineSavedSearchQuery | ClinicalTrialSavedSearchQuery | PatentSavedSearchQuery | DealSavedSearchQuery | RegulatorySavedSearchQuery | EpidemiologySavedSearchQuery | NewsSavedSearchQuery | null);
  query_type?: ('entity_search' | 'chemistry_search' | 'pipeline_search' | 'clinical_trial_search' | 'patent_search' | 'deal_search' | 'regulatory_search' | 'epidemiology_search' | 'news_search' | null);
  visibility?: (SavedSearchVisibility | null);
};
