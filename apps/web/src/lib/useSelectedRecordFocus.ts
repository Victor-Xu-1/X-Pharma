import { useEffect, useRef } from "react";

/** Focus only an explicitly requested record; initial links and background refreshes do not steal focus. */
export function useSelectedRecordFocus(recordId: string | null, ready: boolean) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const requested = useRef<string | null>(null);
  useEffect(() => {
    if (recordId && requested.current === recordId && ready && headingRef.current) {
      headingRef.current.focus();
      requested.current = null;
    }
  }, [recordId, ready]);
  function requestFocus(nextId: string) {
    requested.current = nextId;
    if (nextId === recordId && ready && headingRef.current) {
      headingRef.current.focus();
      requested.current = null;
    }
  }
  return { headingRef, requestFocus };
}
