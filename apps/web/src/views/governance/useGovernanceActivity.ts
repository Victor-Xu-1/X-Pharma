import { useEffect, useRef, useState } from "react";

/** One synchronous operation boundary for the mounted governance workspace. */
export function useGovernanceActivity() {
  const locked = useRef(false);
  const mounted = useRef(true);
  const [intent, setIntent] = useState("");
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return {
    busy: Boolean(intent),
    intent,
    isLocked: () => locked.current,
    isCurrent: () => mounted.current,
    acquire: (next: string) => {
      if (locked.current || !mounted.current) return false;
      locked.current = true;
      setIntent(next);
      return true;
    },
    release: () => {
      locked.current = false;
      if (mounted.current) setIntent("");
    },
  };
}
export type GovernanceActivity = ReturnType<typeof useGovernanceActivity>;
