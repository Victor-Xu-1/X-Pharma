import { expect, it } from "vitest";

import { effectiveSort, parseSortTokens } from "../lib/contracts/sorting";

const fields = new Set(["published_at", "event_type", "publisher", "venue", "title"] as const);

it("preserves ordered criteria, removes duplicate fields, and enforces the five-level cap", () => {
  expect(
    effectiveSort(
      [
        { field: "event_type", direction: "asc" },
        { field: "publisher", direction: "desc" },
        { field: "event_type", direction: "desc" },
        { field: "venue", direction: "asc" },
        { field: "title", direction: "desc" },
        { field: "published_at", direction: "asc" },
      ],
      "event_type",
      "asc",
    ),
  ).toEqual([
    { field: "event_type", direction: "asc" },
    { field: "publisher", direction: "desc" },
    { field: "venue", direction: "asc" },
    { field: "title", direction: "desc" },
  ]);
});

it("resets stale criteria when the compatibility primary sort changes", () => {
  expect(
    effectiveSort(
      [
        { field: "published_at", direction: "desc" },
        { field: "title", direction: "asc" },
      ],
      "event_type",
      "asc",
    ),
  ).toEqual([{ field: "event_type", direction: "asc" }]);
});

it("fails closed to the supplied default for invalid, duplicate, or oversized URL sorting", () => {
  const fallback = { field: "published_at" as const, direction: "desc" as const };

  expect(parseSortTokens(["event_type:asc", "title:desc"], fields, fallback)).toEqual([
    { field: "event_type", direction: "asc" },
    { field: "title", direction: "desc" },
  ]);
  expect(parseSortTokens(["event_type:asc", "event_type:desc"], fields, fallback)).toEqual([fallback]);
  expect(parseSortTokens(["unknown:asc"], fields, fallback)).toEqual([fallback]);
  expect(parseSortTokens(["title:sideways"], fields, fallback)).toEqual([fallback]);
  expect(
    parseSortTokens(
      ["published_at:desc", "event_type:asc", "publisher:asc", "venue:asc", "title:asc", "title:desc"],
      fields,
      fallback,
    ),
  ).toEqual([fallback]);
});
