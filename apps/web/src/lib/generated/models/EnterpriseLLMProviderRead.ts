/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnterpriseLLMProviderRead = {
  active: boolean;
  api_key_configured?: boolean;
  api_key_fingerprint: string;
  base_url: string;
  created_at: string;
  id: string;
  include_schema_in_prompt: boolean;
  last_test_message: (string | null);
  last_test_status: ('passed' | 'failed' | null);
  last_tested_at: (string | null);
  max_output_tokens_per_segment: number;
  model: string;
  name: string;
  priority: number;
  request_attempts: number;
  request_timeout_seconds: number;
  response_format_mode: 'json_schema' | 'json_object' | 'prompt_only';
  thinking_mode: 'provider_default' | 'enabled' | 'disabled';
  updated_at: string;
  version: number;
};
