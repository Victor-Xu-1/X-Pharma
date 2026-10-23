import { useEffect } from "react";
import { startLocaleSynchronization } from "../lib/i18n";

export function LocaleEffects() {
  useEffect(() => startLocaleSynchronization(), []);
  return null;
}
