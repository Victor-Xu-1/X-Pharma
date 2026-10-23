import { expect, it } from "vitest";
import { deliveryDeadCount, queueCount } from "../views/environment/platformMetrics";

it("keeps observed zero distinct from missing, malformed or unsafe queue counts", () => {
  expect(queueCount({ pending: 0 }, "pending")).toBe(0);
  expect(queueCount({ pending: 12 }, "pending")).toBe(12);
  for (const value of [
    null,
    {},
    [],
    { pending: -1 },
    { pending: 1.5 },
    { pending: "0" },
    { pending: Number.NaN },
    { pending: Number.POSITIVE_INFINITY },
    { pending: Number.MAX_SAFE_INTEGER + 1 },
    Object.create({ pending: 4 }),
  ])
    expect(queueCount(value, "pending")).toBeNull();
});

it("does not turn unobserved delivery channels into a zero dead-letter total", () => {
  expect(deliveryDeadCount({})).toBe(0);
  expect(deliveryDeadCount({ search: { dead: 0 }, monitoring: { dead: 4 } })).toBe(4);
  for (const value of [
    null,
    [],
    { search: {} },
    { search: { dead: 4 }, monitoring: { dead: null } },
    { search: { dead: Number.MAX_SAFE_INTEGER }, monitoring: { dead: 1 } },
  ])
    expect(deliveryDeadCount(value)).toBeNull();
});
