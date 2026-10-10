import { act, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { GovernanceRun } from "../lib/contracts/governance";
import { setLocale } from "../lib/i18n";
import { GovernanceRunDetail } from "../views/governance/GovernanceRunDetail";

const run: GovernanceRun = {
  id: "controlled-run",
  source_version_id: "controlled-version",
  source_asset_id: "controlled-asset",
  source_logical_path: "原始文件.pdf",
  source_file_name: "原始文件.pdf",
  source_content_sha256: "a".repeat(64),
  schema_name: "Original schema",
  schema_version: "1.2.3",
  model_provider: "Original provider",
  model_name: "原始 model <Bio>",
  prompt_sha256: "b".repeat(64),
  policy_sha256: "c".repeat(64),
  input_sha256: "d".repeat(64),
  policy_current: true,
  status: "succeeded",
  validation_errors: [],
  input_tokens: 0,
  output_tokens: 0,
  estimated_cost: "0.000000",
  started_at: "2026-01-01T00:00:00Z",
  completed_at: "2026-01-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
};

it("does not turn reported zero usage into unreported metadata", () => {
  render(<GovernanceRunDetail run={run} />);
  expect(screen.queryByText("未上报")).not.toBeInTheDocument();
  expect(screen.getByText("0 / 0.000000")).toBeInTheDocument();
});

it("switches run framing without rewriting source identity, validation errors or fingerprints", () => {
  setLocale("en");
  render(<GovernanceRunDetail run={run} />);
  expect(screen.getByRole("heading", { name: "Execution settings" })).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("heading", { name: "执行配置" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: run.source_file_name })).toBeInTheDocument();
  expect(screen.getByText("Original provider / 原始 model <Bio>")).toBeInTheDocument();
  expect(screen.getByText(run.source_content_sha256)).toBeInTheDocument();
});

it("distinguishes absent usage from a partially reported zero instead of implying complete accounting", () => {
  setLocale("en");
  const view = render(
    <GovernanceRunDetail run={{ ...run, input_tokens: null, output_tokens: 0, estimated_cost: null }} />,
  );
  expect(screen.getByText("Reported tokens (incomplete): 0")).toBeInTheDocument();
  view.rerender(
    <GovernanceRunDetail run={{ ...run, input_tokens: null, output_tokens: null, estimated_cost: null }} />,
  );
  expect(screen.getByText("Not reported")).toBeInTheDocument();
});
