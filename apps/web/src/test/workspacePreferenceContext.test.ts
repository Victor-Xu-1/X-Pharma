import { afterEach, expect, it, vi } from "vitest";

import { saveWorkspaceTablePreference } from "../lib/contracts/workspacePreferences";
import {
  hasPendingSessionWrites,
  setOrganizationSession,
  suspendOrganizationSession,
} from "../lib/organizationSession";

const original = { id: "researcher", tenant_id: "organization-a" };
const alternate = { ...original, tenant_id: "organization-b" };
const preferences = { columnOrder: [], columnVisibility: {}, density: "compact" as const };
const payload = (version: number) => ({
  column_order: [],
  column_visibility: {},
  density: "comfortable",
  persisted: true,
  preference_key: "entity-search",
  schema_version: 1,
  updated_at: null,
  version,
});
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  setOrganizationSession(null);
  vi.restoreAllMocks();
});

it("holds one logical write through conflict reconciliation and retries the captured payload", async () => {
  const intent = { columnOrder: ["name"], columnVisibility: { phase: false }, density: "compact" as const };
  const bodies: unknown[] = [];
  let release: ((response: Response) => void) | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "GET")
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    bodies.push(JSON.parse(String(init?.body)));
    return bodies.length === 1 ? json({ detail: "Version conflict" }, 409) : json(payload(8));
  });
  setOrganizationSession(original);
  const pending = saveWorkspaceTablePreference("entity-search", intent, 1);
  await vi.waitFor(() => expect(release).toBeDefined());
  expect(hasPendingSessionWrites()).toBe(true);
  intent.columnOrder.push("phase");
  intent.columnVisibility.phase = true;
  release?.(json(payload(7)));
  await pending;
  expect(bodies[1]).toEqual({
    column_order: ["name"],
    column_visibility: { phase: false },
    density: "compact",
    expected_version: 7,
    schema_version: 1,
  });
  expect(hasPendingSessionWrites()).toBe(false);
});

it.each(["organization", "account", "round-trip", "suspended"])(
  "does not replay an old preference after the %s context changes",
  async (transition) => {
    const requests: string[] = [];
    let release: ((response: Response) => void) | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
      requests.push(`${init?.method}:${new Headers(init?.headers).get("X-Organization-ID")}`);
      if (requests.length === 1)
        return new Promise<Response>((resolve) => {
          release = resolve;
        });
      return json(payload(7));
    });
    setOrganizationSession(original);
    const pending = saveWorkspaceTablePreference("entity-search", preferences, 1).then(
      () => "resolved",
      () => "rejected",
    );
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    if (transition === "suspended") suspendOrganizationSession();
    else setOrganizationSession(transition === "account" ? { ...original, id: "another" } : alternate);
    if (transition === "round-trip") setOrganizationSession(original);
    release?.(json({ detail: "Version conflict" }, 409));
    expect(await pending).toBe("rejected");
    expect(requests).toEqual(["PUT:organization-a"]);
  },
);

it("checks the context again after reading the conflict version", async () => {
  const requests: string[] = [];
  let release: ((response: Response) => void) | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    requests.push(`${init?.method}:${new Headers(init?.headers).get("X-Organization-ID")}`);
    if (requests.length === 1) return json({ detail: "Version conflict" }, 409);
    if (requests.length === 2)
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    return json(payload(8));
  });
  setOrganizationSession(original);
  const pending = saveWorkspaceTablePreference("entity-search", preferences, 1).then(
    () => "resolved",
    () => "rejected",
  );
  await vi.waitFor(() => expect(requests).toHaveLength(2));
  setOrganizationSession(alternate);
  release?.(json(payload(7)));
  expect(await pending).toBe("rejected");
  expect(requests).toEqual(["PUT:organization-a", "GET:organization-a"]);
});

it("keeps the bounded retry for a refresh of the same account and organization", async () => {
  const methods: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    methods.push(init?.method ?? "GET");
    if (methods.length === 1) {
      setOrganizationSession({ ...original });
      return json({ detail: "Version conflict" }, 409);
    }
    return json(payload(methods.length === 2 ? 7 : 8));
  });
  setOrganizationSession(original);
  await expect(saveWorkspaceTablePreference("entity-search", preferences, 1)).resolves.toMatchObject({ version: 8 });
  expect(methods).toEqual(["PUT", "GET", "PUT"]);
});
