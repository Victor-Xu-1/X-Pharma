import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  type CollectionPolicy,
  collectionsKeys,
  getWorkspaceExportPolicy,
  saveWorkspaceExportPolicy,
} from "../lib/contracts/collections";
import { setLocale } from "../lib/i18n";
import { useWorkspacePolicyDrafts } from "../views/commercial/policy/useWorkspacePolicy";
import { useCommercialOperationBoundary } from "../views/commercial/useCommercialOperationBoundary";
import { WorkspaceExportPolicyPanel } from "../views/WorkspaceExportPolicyPanel";
import { renderWithQueryClient } from "./renderWithQueryClient";

function PolicyHarness() {
  const boundary = useCommercialOperationBoundary();
  const draftState = useWorkspacePolicyDrafts();
  return <WorkspaceExportPolicyPanel boundary={boundary} draftState={draftState} />;
}
vi.mock("../lib/contracts/collections", async (original) => ({
  ...(await original<typeof import("../lib/contracts/collections")>()),
  getWorkspaceExportPolicy: vi.fn(),
  saveWorkspaceExportPolicy: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("zh-CN");
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(null);
});
it("renders policy framing and catalog field groups in English without rewriting draft licensing text", async () => {
  setLocale("en");
  renderWithQueryClient(<PolicyHarness />);
  expect(await screen.findByText("Workspace export policy")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Attribution" })).toHaveValue("Licensed for internal enterprise use");
  expect(screen.getByText("Allowed fields")).toBeInTheDocument();
  expect(screen.getByText("Entity search")).toBeInTheDocument();
});
it("freezes every policy input while the original versioned draft is pending", async () => {
  vi.mocked(saveWorkspaceExportPolicy).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<PolicyHarness />);
  const version = await screen.findByRole("textbox", { name: "策略版本" });
  fireEvent.change(version, { target: { value: "original-policy-v2" } });
  fireEvent.click(screen.getByRole("button", { name: "保存导出策略" }));
  await waitFor(() => expect(saveWorkspaceExportPolicy).toHaveBeenCalledOnce());
  expect(version).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "授权标注" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "CSV" })).toBeDisabled();
  await act(async () => {
    setLocale("en");
  });
  expect(screen.getByRole("textbox", { name: "Policy version" })).toHaveValue("original-policy-v2");
  expect(saveWorkspaceExportPolicy).toHaveBeenCalledOnce();
});
const policy: CollectionPolicy = {
  id: "controlled-policy",
  policy_version: "original-v1",
  policy_sha256: "a".repeat(64),
  enabled: true,
  allowed_formats: ["csv"],
  allowed_fields: ["id", "entity_type", "name", "unknown.source_field"],
  attribution: "Original licensing <source>",
  max_records_per_export: 25,
  configured_by_user_id: "controlled-admin",
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
it("prioritizes policy identity and limits before collapsed field groups without hiding unknown field IDs", async () => {
  setLocale("en");
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  renderWithQueryClient(<PolicyHarness />);
  const version = await screen.findByRole("textbox", { name: "Policy version" });
  const summary = screen.getByText("General fields").closest("summary");
  expect(summary).not.toBeNull();
  expect(version.compareDocumentPosition(summary as HTMLElement) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  expect(summary?.closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("unknown.source_field", { exact: true })).toBeInTheDocument();
  expect(saveWorkspaceExportPolicy).not.toHaveBeenCalled();
});
it("retains an unsent policy when a server update arrives and requires an explicit use-latest decision", async () => {
  setLocale("en");
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  const { queryClient } = renderWithQueryClient(<PolicyHarness />);
  const attribution = await screen.findByRole("textbox", { name: "Attribution" });
  await waitFor(() => expect(attribution).toHaveValue(policy.attribution));
  fireEvent.change(attribution, { target: { value: "Unsubmitted licensing <source>" } });
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue({
    ...policy,
    policy_version: "new-v2",
    attribution: "Updated licensing <source>",
  });
  await act(async () => queryClient.refetchQueries({ queryKey: collectionsKeys.policy, exact: true }));
  const latest = await screen.findByRole("button", { name: "Use latest policy" });
  expect(attribution).toHaveValue("Unsubmitted licensing <source>");
  expect(screen.getByRole("button", { name: "Save export policy" })).toBeDisabled();
  fireEvent.click(latest);
  expect(attribution).toHaveValue("Updated licensing <source>");
  expect(screen.getByRole("textbox", { name: "Policy version" })).toHaveValue("new-v2");
  expect(saveWorkspaceExportPolicy).not.toHaveBeenCalled();
});
it("adopts refreshed policy values when the current draft has no unsent edits", async () => {
  setLocale("en");
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  const { queryClient } = renderWithQueryClient(<PolicyHarness />);
  const attribution = await screen.findByRole("textbox", { name: "Attribution" });
  await waitFor(() => expect(attribution).toHaveValue(policy.attribution));
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue({
    ...policy,
    policy_version: "new-v2",
    attribution: "Updated licensing <source>",
  });
  await act(async () => queryClient.refetchQueries({ queryKey: collectionsKeys.policy, exact: true }));
  await waitFor(() => expect(attribution).toHaveValue("Updated licensing <source>"));
  expect(saveWorkspaceExportPolicy).not.toHaveBeenCalled();
});
