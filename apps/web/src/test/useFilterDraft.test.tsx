import { act, renderHook } from "@testing-library/react";
import { expect, it } from "vitest";

import { useFilterDraft, useSearchFilterDraft } from "../lib/useFilterDraft";

it("keeps a draft across equivalent objects and resets it synchronously for restored conditions", () => {
  const first = { query: "applied", types: ["drug"], offset: 0 };
  const { result, rerender } = renderHook(({ applied }) => useFilterDraft(applied), {
    initialProps: { applied: first },
  });
  act(() => result.current[1]((current) => ({ ...current, query: "draft" })));
  rerender({ applied: { offset: 0, types: ["drug"], query: "applied" } });
  expect(result.current[0].query).toBe("draft");
  const obsoleteUpdate = result.current[1];
  rerender({ applied: { ...first, query: "restored", offset: 20 } });
  expect(result.current[0]).toEqual({ ...first, query: "restored", offset: 20 });
  act(() => obsoleteUpdate({ ...first, query: "obsolete callback" }));
  expect(result.current[0].query).toBe("restored");
  rerender({ applied: first });
  expect(result.current[0].query).toBe("applied");
});

it("preserves unapplied search fields while synchronizing the externally applied sorting", () => {
  const applied = {
    query: "applied",
    sortBy: "name",
    sortDirection: "asc",
    sort: [{ field: "name", direction: "asc" }],
  };
  const { result, rerender } = renderHook(({ value }) => useSearchFilterDraft(value), {
    initialProps: { value: applied },
  });
  act(() => result.current[1]((current) => ({ ...current, query: "unsubmitted 科研" })));
  const obsoleteUpdate = result.current[1];
  const sorted = { ...applied, sortBy: "phase", sortDirection: "desc", sort: [{ field: "phase", direction: "desc" }] };
  rerender({ value: sorted });
  expect(result.current[0]).toEqual({ ...sorted, query: "unsubmitted 科研" });
  act(() => obsoleteUpdate({ ...applied, query: "late obsolete response" }));
  expect(result.current[0].query).toBe("unsubmitted 科研");
  rerender({ value: { ...sorted, query: "restored URL" } });
  expect(result.current[0]).toEqual({ ...sorted, query: "restored URL" });
});
