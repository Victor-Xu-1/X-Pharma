import { expect, it } from "vitest";

import { resolveBrowserCredentials } from "../lib/browserAcceptanceCredentials";

it("derives an isolated account for each governed browser project", () => {
  const environment = {
    E2E_EMAIL_PREFIX: "e2e-20260725033000-12345",
    E2E_PASSWORD: "acceptance-password",
  };

  expect(resolveBrowserCredentials("desktop-1440", environment)).toEqual({
    email: "e2e-20260725033000-12345-desktop-1440@example.test",
    password: "acceptance-password",
  });
  expect(resolveBrowserCredentials("mobile-390", environment)).toEqual({
    email: "e2e-20260725033000-12345-mobile-390@example.test",
    password: "acceptance-password",
  });
});

it("fails closed for unknown projects or unsafe prefixes", () => {
  expect(() =>
    resolveBrowserCredentials("unknown", {
      E2E_EMAIL_PREFIX: "e2e-20260725033000-12345",
      E2E_PASSWORD: "acceptance-password",
    }),
  ).toThrow("Unsupported browser acceptance project");
  expect(() =>
    resolveBrowserCredentials("desktop-1440", {
      E2E_EMAIL_PREFIX: "../../unsafe",
      E2E_PASSWORD: "acceptance-password",
    }),
  ).toThrow("Browser acceptance email prefix is invalid");
  expect(resolveBrowserCredentials("desktop-1440", {})).toBeNull();
});
