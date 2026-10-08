import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { LocaleEffects } from "./components/LocaleEffects";
import { initializeLocale } from "./lib/i18n";
import { appQueryClient } from "./lib/queryClient";
import "./styles.css";
import "./design-system.css";

export function mountApplication(application: ReactElement) {
  const root = document.getElementById("root");
  if (!root) throw new Error("Application root element is missing");
  initializeLocale();

  createRoot(root).render(
    <StrictMode>
      <LocaleEffects />
      <QueryClientProvider client={appQueryClient}>{application}</QueryClientProvider>
    </StrictMode>,
  );
}
