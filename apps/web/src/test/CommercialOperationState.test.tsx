import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { getWorkspaceExportPolicy, saveWorkspaceExportPolicy } from "../lib/contracts/collections";
import {
  type CommercialClient,
  type CommercialOverview,
  commercialKeys,
  executeCommercialOperation,
  loadCommercialClients,
  loadCommercialOverview,
} from "../lib/contracts/commercial";
import { setLocale } from "../lib/i18n";
import { CommercialView } from "../views/CommercialView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/collections", async (original) => ({
  ...(await original<typeof import("../lib/contracts/collections")>()),
  getWorkspaceExportPolicy: vi.fn(),
  saveWorkspaceExportPolicy: vi.fn(),
}));

vi.mock("../lib/contracts/commercial", async (original) => ({
  ...(await original<typeof import("../lib/contracts/commercial")>()),
  loadCommercialOverview: vi.fn(),
  loadCommercialClients: vi.fn(),
  executeCommercialOperation: vi.fn(),
}));
const overview: CommercialOverview = {
  as_of: "2026-10-10T00:00:00Z",
  period_start: "2026-10-10T00:00:00Z",
  subscriptions: [],
  active_client_count: 1,
  open_risk_count: 0,
  pending_export_count: 0,
  dead_billing_delivery_count: 0,
  open_dispute_count: 0,
};
const client: CommercialClient = {
  id: "controlled-client",
  client_key: "ORIGINAL_CLIENT_KEY",
  display_name: "原始 Agent <source>",
  active: true,
  active_reservations: 0,
  available_units: "0.000000001",
  subscription_key: null,
  subscription_status: null,
  billing_account_key: null,
  denial_count_24h: 0,
  subjects: [],
  last_policy_event_at: null,
  created_at: overview.as_of,
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("zh-CN");
  vi.mocked(loadCommercialOverview).mockResolvedValue(overview);
  vi.mocked(loadCommercialClients).mockResolvedValue([client]);
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(null);
});
async function openClientAction() {
  fireEvent.click(await screen.findByRole("tab", { name: "Agent 客户端" }));
  fireEvent.click(await screen.findByRole("button", { name: "停用 " + client.display_name }));
  const dialog = screen.getByRole("dialog", { name: "停用客户端" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "操作原因" }), {
    target: { value: "Original decision <source>" },
  });
  return dialog;
}
it("renders all eight commercial panels in English rather than translating only the outer workspace", async () => {
  setLocale("en");
  renderWithQueryClient(<CommercialView />);
  for (const name of [
    "Contracts & quota",
    "Clients",
    "Billing",
    "Disputes",
    "Exports",
    "Export policy",
    "Risk events",
    "Data lifecycle",
  ]) {
    expect(await screen.findByRole("tab", { name })).toBeInTheDocument();
  }
  expect(await screen.findByRole("button", { name: "Refresh" })).toBeInTheDocument();
});
it("freezes every workspace tab while one captured client operation remains pending", async () => {
  vi.mocked(executeCommercialOperation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<CommercialView />);
  const dialog = await openClientAction();
  fireEvent.click(within(dialog).getByRole("button", { name: "确认停用" }));
  await waitFor(() => expect(executeCommercialOperation).toHaveBeenCalledOnce());
  for (const tab of screen.getAllByRole("tab")) {
    expect(tab).toHaveAttribute("aria-disabled", "true");
    if (tab.getAttribute("aria-selected") !== "true") expect(tab).toBeDisabled();
  }
  fireEvent.click(screen.getByRole("tab", { name: "合同与额度" }));
  expect(screen.getByRole("tab", { name: "Agent 客户端" })).toHaveAttribute("aria-selected", "true");
  expect(dialog).toBeInTheDocument();
});
it("acquires one synchronous intent before two same-tick submissions can execute", async () => {
  vi.mocked(executeCommercialOperation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<CommercialView />);
  const dialog = await openClientAction();
  const form = within(dialog).getByRole("button", { name: "确认停用" }).closest("form");
  if (!form) throw new Error("Commercial action form missing");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await waitFor(() => expect(executeCommercialOperation).toHaveBeenCalledOnce());
});
it("keeps a pending original reason and resource identity while modal framing changes language", async () => {
  vi.mocked(executeCommercialOperation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<CommercialView />);
  const dialog = await openClientAction();
  fireEvent.click(within(dialog).getByRole("button", { name: "确认停用" }));
  await act(async () => {
    setLocale("en");
  });
  const translated = await screen.findByRole("dialog", { name: "Disable client" });
  expect(within(translated).getByRole("textbox", { name: "Reason" })).toHaveValue("Original decision <source>");
  expect(within(translated).getByText(client.client_key)).toBeInTheDocument();
  expect(within(translated).getByRole("textbox", { name: "Reason" })).toBeDisabled();
  expect(executeCommercialOperation).toHaveBeenCalledOnce();
});
it("hides an already opened client intent after its current authoritative read denies access", async () => {
  const { queryClient } = renderWithQueryClient(<CommercialView />);
  await openClientAction();
  vi.mocked(loadCommercialClients).mockRejectedValue(new ApiError("RAW_COMMERCIAL_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: commercialKeys.clients, exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_COMMERCIAL_DENIAL");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryAllByText(client.display_name)).toHaveLength(0);
});
it("does not replace an optional unreported organization count with an observed zero", async () => {
  const { active_client_count: _omitted, ...partial } = overview;
  vi.mocked(loadCommercialOverview).mockResolvedValue(partial);
  renderWithQueryClient(<CommercialView />);
  const label = await screen.findByText("活跃客户端");
  expect(label.closest("div")).toHaveTextContent("未上报");
});
it("uses the same workspace boundary for a policy write and keeps its draft after a rejected response", async () => {
  let reject: (error: Error) => void = () => {
    throw new Error("Pending policy write not installed");
  };
  vi.mocked(saveWorkspaceExportPolicy).mockImplementation(
    () =>
      new Promise((_resolve, rejectRequest) => {
        reject = rejectRequest;
      }),
  );
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "导出策略" }));
  const version = await screen.findByRole("textbox", { name: "策略版本" });
  fireEvent.change(version, { target: { value: "ORIGINAL_POLICY_V2" } });
  fireEvent.click(screen.getByRole("button", { name: "保存导出策略" }));
  await waitFor(() => expect(saveWorkspaceExportPolicy).toHaveBeenCalledOnce());
  expect(screen.getByRole("tab", { name: "Agent 客户端" })).toBeDisabled();
  expect(version).toBeDisabled();
  await act(async () => {
    setLocale("en");
  });
  expect(screen.getByRole("textbox", { name: "Policy version" })).toHaveValue("ORIGINAL_POLICY_V2");
  await act(async () => {
    reject(new Error("RAW_POLICY_WRITE_DENIAL"));
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_POLICY_WRITE_DENIAL");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "Policy version" })).toHaveValue("ORIGINAL_POLICY_V2");
});
it("retains unsent policy drafts across commercial-panel navigation", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "导出策略" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "授权标注" }), {
    target: { value: "Original attribution <source>" },
  });
  fireEvent.click(screen.getByRole("tab", { name: "合同与额度" }));
  fireEvent.click(screen.getByRole("tab", { name: "导出策略" }));
  expect(await screen.findByRole("textbox", { name: "授权标注" })).toHaveValue("Original attribution <source>");
});
