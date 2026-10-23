import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { setLocale } from "../lib/i18n";

it.each([
  ["en", "Commercial operations"],
  ["zh-CN", "商业运营"],
] as const)("uses the concise %s commercial heading without repeating the agent context", (locale, title) => {
  setLocale(locale);
  render(
    <WorkspaceShell
      user={{
        id: "controlled-user",
        tenant_id: "controlled-tenant",
        email: "local@example.test",
        display_name: "Original name",
        role: "admin",
      }}
      activeWorkbench="internal"
      activeView="commercial"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      commercial content
    </WorkspaceShell>,
  );
  expect(screen.getByRole("heading", { name: title, level: 1 })).toBeInTheDocument();
  expect(screen.getByText("Original name")).toBeInTheDocument();
});
