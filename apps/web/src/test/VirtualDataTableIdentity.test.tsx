import { onlineManager } from "@tanstack/react-query";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { SessionIdentityContext } from "../components/SessionIdentityContext";
import { VirtualDataTable } from "../components/VirtualDataTable";
import { type WorkspaceTablePreferenceKey, workspacePreferenceKeys } from "../lib/contracts/workspacePreferences";
import { setOrganizationSession } from "../lib/organizationSession";
import { renderWithQueryClient } from "./renderWithQueryClient";

const user = {
  id: "researcher",
  tenant_id: "organization-a",
  email: "researcher@example.test",
  display_name: "科研",
  role: "analyst" as const,
};
const alternate = { ...user, tenant_id: "organization-b" };
const snapshot = (key: WorkspaceTablePreferenceKey, version: number, density: string) => ({
  column_order: [],
  column_visibility: {},
  density,
  persisted: true,
  preference_key: key,
  schema_version: 1,
  updated_at: null,
  version,
});
const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

function table(identity = user, preferenceKey: WorkspaceTablePreferenceKey = "entity-search") {
  return (
    <SessionIdentityContext value={identity}>
      <VirtualDataTable
        ariaLabel="Preference owner"
        preferenceKey={preferenceKey}
        columns={[{ accessorKey: "name", header: "Name" }]}
        data={[{ id: "record", name: "Original 科研" }]}
        getRowId={(row) => row.id}
      />
    </SessionIdentityContext>
  );
}
afterEach(() => {
  onlineManager.setOnline(true);
  setOrganizationSession(null);
  vi.restoreAllMocks();
});

it.each(["organization", "table"])("never applies the old save to the new %s cache", async (transition) => {
  let release: ((response: Response) => void) | undefined;
  let puts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    if (init?.method === "PUT") {
      puts++;
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    }
    const key = String(url).endsWith("/pipeline") ? "pipeline" : "entity-search";
    return json(snapshot(key, 7, "comfortable"));
  });
  setOrganizationSession(user);
  const view = renderWithQueryClient(table());
  try {
    await waitFor(() => expect(screen.getByRole("button", { name: "紧凑" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
    await waitFor(() => expect(puts).toBe(1));
    const pending = view.queryClient.getMutationCache().getAll()[0];
    const nextUser = transition === "organization" ? alternate : user;
    const nextKey = transition === "table" ? "pipeline" : "entity-search";
    act(() => setOrganizationSession(nextUser));
    view.rerender(table(nextUser, nextKey));
    await waitFor(() => expect(screen.getByRole("button", { name: "标准" })).toBeEnabled());
    await act(async () => {
      release?.(json(snapshot("entity-search", 8, "compact")));
    });
    await waitFor(() => expect(pending.state.status).toBe("error"));
    expect(
      view.queryClient.getQueryData(workspacePreferenceKeys.table(`${nextUser.tenant_id}:${nextUser.id}`, nextKey)),
    ).toMatchObject({ preferenceKey: nextKey, version: 7, density: "comfortable" });
    expect(screen.getByRole("button", { name: "标准" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(puts).toBe(1);
  } finally {
    view.unmount();
    view.queryClient.clear();
  }
});

it("discards an offline queued write before transport when its view has gone", async () => {
  let puts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "PUT") puts++;
    return json(snapshot("entity-search", 7, "comfortable"));
  });
  setOrganizationSession(user);
  const view = renderWithQueryClient(table());
  try {
    await waitFor(() => expect(screen.getByRole("button", { name: "紧凑" })).toBeEnabled());
    act(() => onlineManager.setOnline(false));
    fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
    await waitFor(() => expect(view.queryClient.getMutationCache().getAll()[0]?.state.isPaused).toBe(true));
    const pending = view.queryClient.getMutationCache().getAll()[0];
    view.rerender(<p>Replacement view</p>);
    act(() => onlineManager.setOnline(true));
    await waitFor(() => expect(pending.state.status).toBe("error"));
    expect(puts).toBe(0);
  } finally {
    view.unmount();
    view.queryClient.clear();
  }
});
