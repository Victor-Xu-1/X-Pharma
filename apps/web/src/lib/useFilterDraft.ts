import { hashKey } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useCallback, useState } from "react";

/** Applied URL conditions own resets; parent object identity never owns a draft. */
export function useFilterDraft<Filters extends object>(
  applied: Filters,
  synchronizedKeys: readonly (keyof Filters)[] = [],
): readonly [Filters, Dispatch<SetStateAction<Filters>>] {
  const key = hashKey([applied]);
  const resetKey = hashKey([
    Object.fromEntries(Object.entries(applied).filter(([name]) => !synchronizedKeys.includes(name as keyof Filters))),
  ]);
  const [state, setState] = useState(() => ({ key, resetKey, value: applied }));
  let value = state.value;
  if (state.key !== key) {
    // Adjust only this hook's state during render, before a new query can expose
    // old input. The key guard makes the adjustment finite and synchronous.
    value =
      state.resetKey === resetKey
        ? { ...state.value, ...Object.fromEntries(synchronizedKeys.map((name) => [name, applied[name]])) }
        : applied;
    setState({ key, resetKey, value });
  }
  const update = useCallback<Dispatch<SetStateAction<Filters>>>(
    (action) => {
      setState((current) => {
        // A delayed callback from an obsolete query cannot overwrite a restored one.
        if (current.key !== key) return current;
        const value = typeof action === "function" ? action(current.value) : action;
        return { ...current, value };
      });
    },
    [key],
  );
  return [value, update];
}

/** Sorting executes the applied search; it must not consume unfinished filter input. */
export function useSearchFilterDraft<Filters extends { sortBy: unknown; sortDirection: unknown; sort?: unknown }>(
  applied: Filters,
) {
  return useFilterDraft(applied, ["sortBy", "sortDirection", "sort"]);
}
