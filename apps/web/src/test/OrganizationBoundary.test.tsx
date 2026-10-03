import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOrganizationControls } from "../components/OrganizationContext";
import { SessionBoundary } from "../components/SessionBoundary";
import { switchOrganization } from "../lib/contracts/organizations";
import { loadSession } from "../lib/contracts/session";
import { setOrganizationSession, trackSessionWrite } from "../lib/organizationSession";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/organizations", () => ({ switchOrganization: vi.fn() }));
vi.mock("../lib/contracts/session", () => ({
  loadSession: vi.fn(),
  logout: vi.fn(),
  login: vi.fn(),
  sessionKeys: { current: ["session", "current"] },
}));

const account = {
  id: "same-account",
  tenant_id: "first-org",
  email: "test@example.test",
  display_name: "Identity",
  phone: null,
  avatar_url: null,
  role: "admin" as const,
};
const second = { ...account, tenant_id: "second-org", role: "viewer" as const };
const privateClients: QueryClient[] = [];

function Workspace({ tenantId }: { tenantId: string }) {
  const privateClient = useQueryClient();
  if (!privateClients.includes(privateClient)) privateClients.push(privateClient);
  const controls = useOrganizationControls();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  return (
    <>
      <p>Organization {tenantId}</p>
      <input aria-label="Private draft" value={draft} onChange={(event) => setDraft(event.target.value)} />
      <button
        type="button"
        onClick={() =>
          void controls?.switchOrganization("second-org").catch((reason: Error) => setError(reason.message))
        }
      >
        Switch organization
      </button>
      {error ? <p role="alert">{error}</p> : null}
    </>
  );
}

function renderBoundary() {
  return renderWithQueryClient(
    <SessionBoundary workbench="research">{({ user }) => <Workspace tenantId={user.tenant_id} />}</SessionBoundary>,
    undefined,
    (client) => client.setQueryData(["private", "results"], ["old organization record"]),
  );
}

describe("organization switch lifecycle", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    privateClients.length = 0;
    setOrganizationSession(null);
    vi.mocked(loadSession).mockResolvedValue({ mode: "local", user: account });
    window.history.replaceState(null, "", "/workspace/research?entity=old-organization-entity");
  });

  it("unmounts the old workspace and evicts private state before confirming the new identity", async () => {
    let complete: (() => void) | undefined;
    vi.mocked(switchOrganization).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = () => resolve(second);
        }),
    );
    const { queryClient } = renderBoundary();
    await screen.findByText("Organization first-org");
    fireEvent.change(screen.getByLabelText("Private draft"), { target: { value: "old private text" } });
    vi.mocked(loadSession).mockResolvedValue({ mode: "local", user: second });
    fireEvent.click(screen.getByRole("button", { name: "Switch organization" }));
    await screen.findByText("正在确认组织会话");
    expect(screen.queryByText("Organization first-org")).not.toBeInTheDocument();
    await waitFor(() => expect(queryClient.getQueryData(["private", "results"])).toBeUndefined());
    await act(async () => complete?.());
    await screen.findByText("Organization second-org");
    expect(screen.getByLabelText("Private draft")).toHaveValue("");
    expect(window.location.search).toBe("");
  });

  it("keeps an ambiguous network result locked until a real identity read succeeds", async () => {
    vi.mocked(switchOrganization).mockRejectedValue(new Error("Network interrupted"));
    const { queryClient } = renderBoundary();
    await screen.findByText("Organization first-org");
    vi.mocked(loadSession).mockRejectedValueOnce(new Error("Offline"));
    fireEvent.click(screen.getByRole("button", { name: "Switch organization" }));
    await screen.findByText("组织会话尚未确认，已暂停工作台以保护数据隔离");
    expect(screen.queryByText("Organization first-org")).not.toBeInTheDocument();
    expect(queryClient.getQueryData(["private", "results"])).toBeUndefined();
    vi.mocked(loadSession).mockResolvedValueOnce({ mode: "local", user: second });
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await screen.findByText("Organization second-org");
  });

  it("isolates late old-organization callbacks from the new organization's query cache", async () => {
    renderBoundary();
    await screen.findByText("Organization first-org");
    const oldClient = privateClients.at(-1);
    expect(oldClient).toBeDefined();
    oldClient?.setQueryData(["protected", "records"], ["private first organization record"]);
    vi.mocked(switchOrganization).mockResolvedValueOnce(second);
    vi.mocked(loadSession).mockResolvedValueOnce({ mode: "local", user: second });
    fireEvent.click(screen.getByRole("button", { name: "Switch organization" }));
    await screen.findByText("Organization second-org");
    const newClient = privateClients.at(-1);
    expect(newClient).not.toBe(oldClient);
    oldClient?.setQueryData(["protected", "records"], ["late old callback"]);
    expect(newClient?.getQueryData(["protected", "records"])).toBeUndefined();
  });

  it("does not interrupt an active write or hide a rejected switch", async () => {
    renderBoundary();
    await screen.findByText("Organization first-org");
    const release = trackSessionWrite("POST");
    fireEvent.click(screen.getByRole("button", { name: "Switch organization" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("操作正在提交");
    expect(switchOrganization).not.toHaveBeenCalled();
    release();
    vi.mocked(switchOrganization).mockRejectedValueOnce(new Error("Forbidden"));
    fireEvent.click(screen.getByRole("button", { name: "Switch organization" }));
    await screen.findByText("未完成组织切换；已重新确认当前会话，请打开组织菜单重试。");
    expect(screen.getByText("Organization first-org")).toBeInTheDocument();
  });
});
