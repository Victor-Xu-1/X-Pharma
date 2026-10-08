import { useCallback, useLayoutEffect, useRef } from "react";

/** Keep an event handler's identity stable while invoking only the latest committed callback. */
export function useCommittedCallback<Arguments extends unknown[]>(
  callback: ((...args: Arguments) => void) | undefined,
) {
  const committed = useRef(callback);
  useLayoutEffect(() => {
    committed.current = callback;
  }, [callback]);
  return useCallback((...args: Arguments) => {
    committed.current?.(...args);
  }, []);
}
