import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { SessionIdentityContext } from "../components/SessionIdentityContext";
import { VirtualDataTable } from "../components/VirtualDataTable";
import { setOrganizationSession } from "../lib/organizationSession";
import { renderWithQueryClient } from "./renderWithQueryClient";

type Sorting = { id: string; desc: boolean }[];
const user = {
  id: "researcher",
  tenant_id: "organization-a",
  email: "researcher@example.test",
  display_name: "科研",
  role: "analyst" as const,
};
const snapshot = (version: number, density: string) => ({
  column_order: [],
  column_visibility: {},
  density,
  persisted: true,
  preference_key: "entity-search",
  schema_version: 1,
  updated_at: null,
  version,
});
const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  setOrganizationSession(null);
  vi.restoreAllMocks();
});

async function setup() {
  let release: ((response: Response) => void) | undefined;
  const sortCalls: Sorting[] = [];
  let puts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "PUT") {
      puts++;
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    }
    return json(snapshot(1, "compact"));
  });
  function Host() {
    const [sorting, setSorting] = useState<Sorting>([{ id: "name", desc: true }]);
    return (
      <SessionIdentityContext value={user}>
        <VirtualDataTable
          ariaLabel="Reset intent table"
          preferenceKey="entity-search"
          columns={[
            { accessorKey: "name", header: "Name" },
            { accessorKey: "phase", header: "Phase" },
          ]}
          data={[{ id: "record-one", name: "Original source data 科研", phase: "2" }]}
          getRowId={(row) => row.id}
          sorting={sorting}
          defaultSorting={[{ id: "name", desc: false }]}
          onSortingChange={(next) => {
            sortCalls.push(next);
            setSorting(next);
          }}
        />
      </SessionIdentityContext>
    );
  }
  setOrganizationSession(user);
  const view = renderWithQueryClient(<Host />);
  await waitFor(() => expect(screen.getByRole("button", { name: "恢复表格默认视图" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "恢复表格默认视图" }));
  await waitFor(() => expect(puts).toBe(1));
  const pending = view.queryClient.getMutationCache().getAll()[0];
  return {
    view,
    sortCalls,
    finish: async () => {
      await act(async () => {
        release?.(json(snapshot(2, "comfortable")));
      });
      await waitFor(() => expect(pending.state.status).not.toBe("pending"));
    },
  };
}

it("keeps a later sort choice while a preference reset save is pending", async () => {
  const { view, sortCalls, finish } = await setup();
  try {
    fireEvent.click(screen.getByRole("button", { name: "Phase" }));
    expect(sortCalls).toEqual([[{ id: "phase", desc: false }]]);
    await finish();
    expect(sortCalls).toEqual([[{ id: "phase", desc: false }]]);
    expect(screen.getByRole("columnheader", { name: "Phase" })).toHaveAttribute("aria-sort", "ascending");
  } finally {
    view.unmount();
    view.queryClient.clear();
  }
});

it("does not call the old sort callback after leaving the table", async () => {
  const { view, sortCalls, finish } = await setup();
  try {
    view.rerender(<div>Replacement view</div>);
    await finish();
    expect(screen.getByText("Replacement view")).toBeVisible();
    expect(sortCalls).toEqual([]);
  } finally {
    view.unmount();
    view.queryClient.clear();
  }
});

it("resets sorting after a successful reset when the view and user intent are still current", async () => {
  const { view, sortCalls, finish } = await setup();
  try {
    await finish();
    expect(sortCalls).toEqual([[{ id: "name", desc: false }]]);
    expect(screen.getByRole("button", { name: "标准" })).toHaveAttribute("aria-pressed", "true");
  } finally {
    view.unmount();
    view.queryClient.clear();
  }
});
