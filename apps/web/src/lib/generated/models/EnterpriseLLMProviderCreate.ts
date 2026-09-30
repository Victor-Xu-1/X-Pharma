/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnterpriseLLMProviderCreate = {
  api_key: string;
  base_url: string;
  include_schema_in_prompt?: boolean;
  max_output_tokens_per_segment?: number;
  model: string;
  name: string;
  reason: string;
  request_attempts?: number;
  request_timeout_seconds?: number;
  response_format_mode?: 'json_schema' | 'json_object' | 'prompt_only';
  thinking_mode?: 'provider_default' | 'enabled' | 'disabled';
};
