import { fireEvent, screen } from "@testing-library/react";
import { Suspense } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { ExplorerRoute } from "../workspaces/research/ExplorerRoute";
import { useResearchNavigation } from "../workspaces/research/useResearchNavigation";
import { renderWithQueryClient } from "./renderWithQueryClient";

type ExplorerProps = Parameters<typeof import("../views/ExplorerView")["ExplorerView"]>[0];

vi.mock("../lib/rum", () => ({ startResearchRum: async () => undefined }));
vi.mock("../views/ExplorerView", () => ({
  ExplorerView: (props: ExplorerProps) => (
    <>
      <label>
        <input
          type="checkbox"
          checked={props.initialIncludeRelated}
          onChange={(event) =>
            props.onSearchChange(
              props.initialQuery,
              props.initialEntityTypes ?? [],
              "verified",
              "relevance",
              "desc",
              0,
              undefined,
              event.target.checked,
            )
          }
        />
        包含已验证关联
      </label>
      <button
        type="button"
        onClick={() =>
          props.onSearchChange("ALK", ["target"], "verified", "name", "asc", 100, [{ field: "name", direction: "asc" }])
        }
      >
        执行查询
      </button>
    </>
  ),
}));

afterEach(() => window.history.replaceState(null, "", "/"));

it("preserves the applied display and analysis mode when executing filters, sorting or pagination", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=explorer&q=EGFR&display=landscape&analysis_view=table",
  );
  function Harness() {
    const navigation = useResearchNavigation();
    return (
      <Suspense fallback="加载">
        <ExplorerRoute
          context={{
            ...navigation,
            user: { id: "user", tenant_id: "tenant", email: "user@example.test", display_name: "User", role: "viewer" },
            onLogout: vi.fn(),
            onUserUpdated: vi.fn(),
            logoutPending: false,
            logoutError: null,
          }}
        />
      </Suspense>
    );
  }
  renderWithQueryClient(<Harness />);
  fireEvent.click(await screen.findByRole("button", { name: "执行查询" }));
  const parameters = new URLSearchParams(window.location.search);
  expect(parameters.get("q")).toBe("ALK");
  expect(parameters.get("offset")).toBe("100");
  expect(parameters.getAll("sort")).toEqual(["name:asc"]);
  expect(parameters.get("display")).toBe("landscape");
  expect(parameters.get("analysis_view")).toBe("table");
});

it("commits the controlled related-search switch urgently and preserves the applied query", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=explorer&q=EGFR&types=drug%2Ctarget&offset=100");
  const updates = vi.fn();
  function Harness() {
    const navigation = useResearchNavigation();
    return (
      <Suspense fallback="加载">
        <ExplorerRoute
          context={{
            ...navigation,
            navigate: (...args) => {
              updates(...args);
              navigation.navigate(...args);
            },
            user: { id: "user", tenant_id: "tenant", email: "user@example.test", display_name: "User", role: "viewer" },
            onLogout: vi.fn(),
            onUserUpdated: vi.fn(),
            logoutPending: false,
            logoutError: null,
          }}
        />
      </Suspense>
    );
  }
  renderWithQueryClient(<Harness />);
  fireEvent.click(await screen.findByRole("checkbox", { name: "包含已验证关联" }));
  expect(updates).toHaveBeenCalledWith(
    expect.objectContaining({
      query: "EGFR",
      entityTypes: expect.arrayContaining(["drug", "target"]),
      entityIncludeRelated: false,
      offset: 0,
    }),
    true,
    true,
  );
  expect(screen.getByRole("checkbox", { name: "包含已验证关联" })).not.toBeChecked();
  expect(new URLSearchParams(window.location.search).get("related")).toBe("0");
  fireEvent.click(screen.getByRole("checkbox", { name: "包含已验证关联" }));
  expect(updates).toHaveBeenLastCalledWith(expect.objectContaining({ entityIncludeRelated: true }), true, true);
  expect(screen.getByRole("checkbox", { name: "包含已验证关联" })).toBeChecked();
  expect(new URLSearchParams(window.location.search).get("related")).toBeNull();
});
