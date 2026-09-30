/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AppliedFilterRead = {
  field: string;
  operator: 'contains' | 'eq' | 'in' | 'gte' | 'lte';
  value: (string | boolean | number | Array<string>);
};
