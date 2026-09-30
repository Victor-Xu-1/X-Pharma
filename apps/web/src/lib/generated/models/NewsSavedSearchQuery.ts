/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type NewsSavedSearchQuery = {
  analysis_view?: 'chart' | 'table';
  content_scope?: (string | null);
  display_mode?: 'list' | 'timeline' | 'landscape';
  entity_id?: (string | null);
  event_type?: ('news' | 'press_release' | 'corporate_announcement' | 'publication' | 'conference_abstract' | 'poster' | 'presentation' | 'other' | null);
  language?: (string | null);
  published_from?: (string | null);
  published_to?: (string | null);
  publisher?: (string | null);
  'q'?: (string | null);
  sort?: Array<string>;
  sort_by?: 'published_at' | 'title' | 'event_type' | 'publisher' | 'venue';
  sort_direction?: 'asc' | 'desc';
  venue?: (string | null);
};
