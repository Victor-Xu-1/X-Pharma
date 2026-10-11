import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { setLocale } from "../lib/i18n";

it.each(["research", "internal"] as const)(
  "keeps one %s language control in the compact topbar without resetting page drafts",
  (workbench) => {
    let compact = true;
    let update: (() => void) | undefined;
    vi.stubGlobal("matchMedia", (media: string) => ({
      media,
      get matches() {
        return compact;
      },
      addEventListener: (_event: string, listener: () => void) => {
        update = listener;
      },
      removeEventListener: vi.fn(),
    }));
    try {
      setLocale("en");
      render(
        <WorkspaceShell
          user={{
            id: "user",
            tenant_id: "tenant",
            email: "user@example.test",
            display_name: "Original 科研",
            role: "admin",
          }}
          activeWorkbench={workbench}
          activeView={workbench === "research" ? "evidence" : "factory"}
          onView={vi.fn()}
          onLogout={vi.fn()}
        >
          <input aria-label="Original research draft" defaultValue="原始 EGFR" />
        </WorkspaceShell>,
      );
      const language = screen.getByRole("combobox", { name: "Interface language" });
      expect(language.closest(".topbar")).not.toBeNull();
      expect(document.querySelector(".page-heading select")).toBeNull();
      fireEvent.change(language, { target: { value: "zh-CN" } });
      expect(screen.getAllByRole("combobox", { name: "界面语言" })).toHaveLength(1);
      expect(screen.getByRole("textbox", { name: "Original research draft" })).toHaveValue("原始 EGFR");
      act(() => {
        compact = false;
        update?.();
      });
      const desktopLanguage = screen.getByRole("combobox", { name: "界面语言" });
      expect(desktopLanguage).toHaveValue("zh-CN");
      expect(desktopLanguage.closest(".page-heading")).not.toBeNull();
      expect(document.querySelector(".topbar select")).toBeNull();
      expect(screen.getByRole("textbox", { name: "Original research draft" })).toHaveValue("原始 EGFR");
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
