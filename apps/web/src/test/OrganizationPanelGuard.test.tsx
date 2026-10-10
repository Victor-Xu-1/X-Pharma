import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { OrganizationContext } from "../components/OrganizationContext";
import { OrganizationPanel } from "../components/OrganizationPanel";
import { ApiError } from "../lib/api";
import { joinOrganization, loadOrganizations, organizationKeys } from "../lib/contracts/organizations";
import type { OrganizationRead } from "../lib/generated";
import { setLocale } from "../lib/i18n";
import { hasPendingSessionWrites } from "../lib/organizationSession";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/organizations", async (original) => ({
  ...(await original<typeof import("../lib/contracts/organizations")>()),
  joinOrganization: vi.fn(),
  loadOrganizations: vi.fn(),
}));
const organization: OrganizationRead = {
  tenant_id: "organization-a",
  slug: "original",
  name: "Original organization 科研",
  role: "admin",
  selected: true,
  active: true,
};
const switchOrganization = vi.fn<(_id: string) => Promise<void>>();
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(loadOrganizations).mockResolvedValue([organization]);
  switchOrganization.mockResolvedValue(undefined);
});
async function openPanel() {
  const rendered = renderWithQueryClient(
    <OrganizationContext value={{ switchOrganization, organizationName: organization.name }}>
      <OrganizationPanel />
    </OrganizationContext>,
  );
  fireEvent.click(screen.getByRole("button", { name: "组织与账号" }));
  await screen.findByText(organization.name, { selector: "strong" });
  return rendered;
}
function invitationForm() {
  const button = screen.getByRole("button", { name: "确认加入组织" });
  const form = button.closest("form");
  if (!form) throw new Error("Organization invitation form is missing");
  fireEvent.change(screen.getByLabelText("管理员邀请码"), { target: { value: "CONTROLLED-NOT-A-REAL-CODE" } });
  fireEvent.click(screen.getByRole("checkbox"));
  return form;
}

it("holds one invitation intent and prevents input, close and Escape until it settles", async () => {
  let finish: ((value: OrganizationRead) => void) | undefined;
  vi.mocked(joinOrganization).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const { queryClient } = await openPanel();
  const form = invitationForm();
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  expect(joinOrganization).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("管理员邀请码")).toBeDisabled();
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(queryClient.getMutationCache().getAll()).toEqual([]);
  expect(hasPendingSessionWrites()).toBe(true);
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Administrator invitation code")).toHaveValue("CONTROLLED-NOT-A-REAL-CODE");
  expect(joinOrganization).toHaveBeenCalledTimes(1);
  await act(async () => finish?.(organization));
  expect(await screen.findByText("Organization joined. Select it above to switch.")).toBeInTheDocument();
  expect(screen.getByLabelText("Administrator invitation code")).toHaveValue("");
  expect(hasPendingSessionWrites()).toBe(false);
});

it("keeps the dialog locked while the current membership catalog is reconciled", async () => {
  let finishRead: ((value: OrganizationRead[]) => void) | undefined;
  await openPanel();
  vi.mocked(joinOrganization).mockResolvedValue(organization);
  vi.mocked(loadOrganizations).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishRead = resolve;
      }),
  );
  fireEvent.submit(invitationForm());
  await waitFor(() => expect(loadOrganizations).toHaveBeenCalledTimes(2));
  expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
  expect(screen.getByLabelText("管理员邀请码")).toBeDisabled();
  await act(async () => finishRead?.([organization]));
  expect(await screen.findByText("已加入组织，请从上方选择切换。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "关闭" })).toBeEnabled();
});

it("does not accept an invitation while the current membership read has failed", async () => {
  const { queryClient } = await openPanel();
  const form = invitationForm();
  const query = queryClient.getQueryCache().find({ queryKey: organizationKeys.own });
  act(() => query?.setState({ status: "error", error: new ApiError("Denied", 403, null), fetchStatus: "idle" }));
  fireEvent.submit(form);
  expect(joinOrganization).not.toHaveBeenCalled();
  expect(screen.getByLabelText("管理员邀请码")).toHaveValue("");
  expect(screen.getByRole("button", { name: "确认加入组织" })).toBeDisabled();
});

it("sanitizes unknown invitation failures and releases the form for an explicit new attempt", async () => {
  await openPanel();
  vi.mocked(joinOrganization).mockRejectedValue(new ApiError("private provider location", 500, null));
  fireEvent.submit(invitationForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("邀请接受失败，请重试");
  expect(screen.queryByText("private provider location")).not.toBeInTheDocument();
  expect(screen.getByLabelText("管理员邀请码")).toHaveValue("");
  act(() => setLocale("en"));
  expect(screen.getByRole("alert")).toHaveTextContent("Could not accept the invitation. Please try again.");
  expect(hasPendingSessionWrites()).toBe(false);
});

it("does not echo an invitation code returned in a validation failure", async () => {
  await openPanel();
  vi.mocked(joinOrganization).mockRejectedValue(new ApiError("Rejected CONTROLLED-NOT-A-REAL-CODE", 400, null));
  fireEvent.submit(invitationForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("邀请接受失败，请重试");
  expect(screen.getByRole("alert")).not.toHaveTextContent("CONTROLLED-NOT-A-REAL-CODE");
});

it("distinguishes accepted membership from a failed catalog refresh without replaying the invitation", async () => {
  await openPanel();
  vi.mocked(joinOrganization).mockResolvedValue(organization);
  vi.mocked(loadOrganizations).mockRejectedValueOnce(new ApiError("Controlled read failure", 503, null));
  fireEvent.submit(invitationForm());
  expect(await screen.findByText("已加入组织，请重试成员资格读取后再切换。")).toBeInTheDocument();
  expect(screen.getByLabelText("管理员邀请码")).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  await screen.findByText(organization.name, { selector: "strong" });
  expect(joinOrganization).toHaveBeenCalledTimes(1);
});

it("does not let a late invitation completion reconcile an unmounted organization dialog", async () => {
  let finish: ((value: OrganizationRead) => void) | undefined;
  const { unmount } = await openPanel();
  vi.mocked(joinOrganization).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  fireEvent.submit(invitationForm());
  unmount();
  await act(async () => finish?.(organization));
  expect(loadOrganizations).toHaveBeenCalledTimes(1);
  expect(hasPendingSessionWrites()).toBe(false);
});

it("captures a current active switch target and blocks a second same-tick switch", async () => {
  const other = { ...organization, tenant_id: "organization-b", selected: false, name: "Other original organization" };
  vi.mocked(loadOrganizations).mockResolvedValue([organization, other]);
  let finish: (() => void) | undefined;
  switchOrganization.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await openPanel();
  const button = screen.getByRole("button", { name: "切换到 Other original organization" });
  act(() => {
    fireEvent.click(button);
    fireEvent.click(button);
  });
  expect(switchOrganization).toHaveBeenCalledTimes(1);
  expect(switchOrganization).toHaveBeenCalledWith("organization-b");
  expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
  await act(async () => finish?.());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
