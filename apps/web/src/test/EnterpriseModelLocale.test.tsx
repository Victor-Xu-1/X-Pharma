import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { EnterpriseLLMProvider } from "../lib/contracts/enterprise";
import { setLocale } from "../lib/i18n";
import { LLMProviderModal } from "../views/enterprise/LLMProviderModal";
import { LLMProvidersPanel } from "../views/enterprise/ModelsPanel";

const provider: EnterpriseLLMProvider = {
  id: "controlled-provider",
  name: "Original provider <source>",
  model: "ORIGINAL_MODEL",
  base_url: "https://provider.example/v1",
  active: true,
  priority: 2,
  version: 1,
  api_key_fingerprint: "CONTROLLED_FINGERPRINT",
  include_schema_in_prompt: true,
  response_format_mode: "prompt_only",
  thinking_mode: "disabled",
  max_output_tokens_per_segment: 16384,
  request_timeout_seconds: 120,
  request_attempts: 2,
  created_at: "2026-10-11T00:00:00Z",
  updated_at: "2026-10-11T00:00:00Z",
  last_tested_at: null,
  last_test_status: null,
  last_test_message: null,
};
beforeEach(() => setLocale("en"));
it("keeps the visible primary row consistent with the effective ordered primary when no provider has priority zero", () => {
  render(
    <LLMProvidersPanel
      providers={[provider]}
      busy=""
      onCreate={vi.fn()}
      onEdit={vi.fn()}
      onPrimary={vi.fn()}
      onTest={vi.fn()}
    />,
  );
  const row = screen.getByRole("row", { name: /Original provider/ });
  expect(within(row).getByText("Primary", { exact: true })).toBeInTheDocument();
  expect(within(row).queryByText("Fallback 2", { exact: true })).not.toBeInTheDocument();
});
it("retains provider input and its unsubmitted credential when only interface language changes", async () => {
  const submit = vi.fn();
  render(<LLMProviderModal action={{ kind: "create" }} busy={false} close={vi.fn()} submit={submit} />);
  fireEvent.change(screen.getByRole("textbox", { name: "Provider name" }), {
    target: { value: "Original unsubmitted <source>" },
  });
  fireEvent.change(screen.getByLabelText("API Key"), { target: { value: "CONTROLLED_UNSUBMITTED_CREDENTIAL" } });
  await act(async () => setLocale("zh-CN"));
  expect(screen.getByRole("textbox", { name: "供应商名称" })).toHaveValue("Original unsubmitted <source>");
  expect(screen.getByLabelText("API Key")).toHaveValue("CONTROLLED_UNSUBMITTED_CREDENTIAL");
  expect(submit).not.toHaveBeenCalled();
});
it("does not present a provider-specific adoption recommendation as the empty configuration requirement", () => {
  render(
    <LLMProvidersPanel
      providers={[]}
      busy=""
      onCreate={vi.fn()}
      onEdit={vi.fn()}
      onPrimary={vi.fn()}
      onTest={vi.fn()}
    />,
  );
  expect(screen.getByText("No active model provider. Configure an approved provider first.")).toBeInTheDocument();
  expect(screen.queryByText(/first.*MiMo/i)).not.toBeInTheDocument();
});
