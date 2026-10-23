import { useEffect, useRef, useState } from "react";
import type { MessageParameters } from "../../lib/i18n";
import { useLocale } from "../../lib/i18n";
import { type factoryMessages, factoryText as t } from "../../lib/i18n/dataFactory";
import { SourceDraftValidationError } from "./sourceDraftValidation";

type Message = keyof typeof factoryMessages;
type Failure = { kind: "raw"; message: string } | { kind: "interface"; key: Message; parameters?: MessageParameters };

/** One in-flight intent per owning controller; raw provider errors are never localized. */
export function useFactoryOperation() {
  useLocale();
  const locked = useRef(false);
  const mounted = useRef(true);
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState<Failure | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function execute(key: string, fallback: Message, work: (current: () => boolean) => Promise<void>) {
    if (locked.current || !mounted.current) return false;
    locked.current = true;
    setBusy(key);
    setFailure(null);
    try {
      await work(() => mounted.current);
      return true;
    } catch (caught) {
      if (mounted.current)
        setFailure(
          caught instanceof SourceDraftValidationError
            ? { kind: "interface", key: caught.key, parameters: caught.parameters }
            : caught instanceof Error
              ? { kind: "raw", message: caught.message }
              : { kind: "interface", key: fallback },
        );
      return false;
    } finally {
      locked.current = false;
      if (mounted.current) setBusy("");
    }
  }
  return {
    busy,
    error: failure ? (failure.kind === "raw" ? failure.message : t(failure.key, failure.parameters)) : "",
    execute,
    isLocked: () => locked.current,
    clear: () => setFailure(null),
    reject: (key: Message) => setFailure({ kind: "interface", key }),
  };
}
