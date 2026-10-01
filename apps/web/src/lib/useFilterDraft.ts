import { hashKey } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useCallback, useState } from "react";

/** Applied URL conditions own resets; parent object identity never owns a draft. */
export function useFilterDraft<Filters extends object>(
  applied: Filters,
): readonly [Filters, Dispatch<SetStateAction<Filters>>] {
  const key = hashKey([applied]);
  const [state, setState] = useState(() => ({ key, value: applied }));
  if (state.key !== key) {
    // Adjust only this hook's state during render, before a new query can expose
    // old input. The key guard makes the adjustment finite and synchronous.
    setState({ key, value: applied });
  }
  const update = useCallback<Dispatch<SetStateAction<Filters>>>(
    (action) => {
      setState((current) => {
        // A delayed callback from an obsolete query cannot overwrite a restored one.
        if (current.key !== key) return current;
        const value = typeof action === "function" ? action(current.value) : action;
        return { key, value };
      });
    },
    [key],
  );
  return [state.key === key ? state.value : applied, update];
}
