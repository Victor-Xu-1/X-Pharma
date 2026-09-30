/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WebVitalSampleCreate = {
  metric_name: 'CLS' | 'INP' | 'LCP' | 'TTFB';
  navigation_sequence: number;
  navigation_type: 'navigate' | 'reload' | 'back-forward' | 'back-forward-cache' | 'prerender' | 'restore' | 'soft-navigation';
  rating: 'good' | 'needs-improvement' | 'poor';
  route: 'overview' | 'explorer' | 'chemistry' | 'pipeline' | 'trials' | 'patents' | 'deals' | 'regulatory' | 'epidemiology' | 'news' | 'target' | 'drug' | 'company' | 'disease' | 'entity' | 'evidence' | 'knowledge' | 'monitoring' | 'collections' | 'unknown';
  value: number;
  viewport_class: 'desktop' | 'tablet' | 'mobile';
};
