import { afterEach, describe, expect, it } from "vitest";

import {
  hasPendingSessionWrites,
  organizationHeaders,
  setOrganizationSession,
  suspendOrganizationSession,
  trackSessionWrite,
} from "../lib/organizationSession";

afterEach(() => setOrganizationSession(null));

describe("organization request boundary", () => {
  it("binds protected requests to the expected account and organization", () => {
    setOrganizationSession({ id: "account-a", tenant_id: "organization-a" });
    const original = organizationHeaders("/api/v1/entities", "POST");
    setOrganizationSession({ id: "account-a", tenant_id: "organization-b" });
    expect(original).toEqual({ "X-Organization-ID": "organization-a", "X-Account-ID": "account-a" });
    expect(organizationHeaders("/api/v1/entities")).toEqual({
      "X-Organization-ID": "organization-b",
      "X-Account-ID": "account-a",
    });
  });

  it("suspends business requests while allowing authenticated identity confirmation", () => {
    setOrganizationSession({ id: "account-a", tenant_id: "organization-a" });
    suspendOrganizationSession();
    expect(() => organizationHeaders("/api/v1/entities")).toThrow("确认中");
    expect(organizationHeaders("/api/v1/auth/me")).toEqual({});
    expect(organizationHeaders("/api/v1/auth/organizations/switch", "POST")["X-Organization-ID"]).toBe(
      "organization-a",
    );
    expect(() => organizationHeaders("/api/v1/auth/me", "PATCH")).toThrow("确认中");
  });

  it("tracks writes and releases once, including cancellation/error cleanup", () => {
    const release = trackSessionWrite("POST");
    expect(hasPendingSessionWrites()).toBe(true);
    release();
    release();
    expect(hasPendingSessionWrites()).toBe(false);
    trackSessionWrite("GET")();
    expect(hasPendingSessionWrites()).toBe(false);
  });
});
