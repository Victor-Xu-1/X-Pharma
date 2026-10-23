import { useEffect, useRef, useState } from "react";
import { hasPendingSessionWrites, trackSessionWrite } from "../../lib/organizationSession";

type OperationKind = "profile" | "password" | "join" | "switch";
export const pendingIdentityMessage = "操作正在提交，请等待完成后再尝试。";

/** One mounted identity surface owns the intent. Secret payloads/results never enter mutation history. */
export function useIdentityOperation() {
  const locked = useRef(false);
  const lifecycle = useRef({ mounted: true, generation: 0 });
  const [pending, setPending] = useState<OperationKind | null>(null);
  useEffect(() => {
    lifecycle.current.mounted = true;
    lifecycle.current.generation += 1;
    return () => {
      lifecycle.current.mounted = false;
      lifecycle.current.generation += 1;
    };
  }, []);
  async function run<T>(
    kind: OperationKind,
    work: (current: () => boolean) => Promise<T>,
    success: (value: T) => void,
    failure: (error: unknown) => void,
  ) {
    if (locked.current || !lifecycle.current.mounted) return false;
    if (hasPendingSessionWrites()) {
      failure(new Error(pendingIdentityMessage));
      return false;
    }
    locked.current = true;
    const generation = lifecycle.current.generation;
    const current = () => lifecycle.current.mounted && lifecycle.current.generation === generation;
    // Organization switching already delegates its complete lifecycle to SessionBoundary.
    const release = kind === "switch" ? () => {} : trackSessionWrite("POST");
    setPending(kind);
    try {
      const value = await work(current);
      if (!current()) return false;
      success(value);
      return true;
    } catch (error) {
      if (current()) failure(error);
      return false;
    } finally {
      locked.current = false;
      release();
      if (current()) setPending(null);
    }
  }
  return { pending, isLocked: () => locked.current, run };
}
