import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getWorkspaceExportPolicy, saveWorkspaceExportPolicy } from "../lib/contracts/collections";
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
