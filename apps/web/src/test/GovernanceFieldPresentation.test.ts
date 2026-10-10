import { expect, it } from "vitest";
import { governanceLabel } from "../lib/governancePresentation";

it("preserves unknown prototype-like field codes literally instead of treating inherited members as vocabulary", () => {
  expect(governanceLabel("constructor")).toBe("constructor");
  expect(governanceLabel("__proto__")).toBe("__proto__");
  expect(governanceLabel("value.toString")).toBe("数值 / toString");
});
