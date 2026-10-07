import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, StatusBadge } from "../components/common";
import { WorkspaceShell } from "../components/WorkspaceShell";

function style(file: string) {
  const relative = `../styles/${file}`;
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}

describe("frontend craft regression boundaries", () => {
  it("keeps a conflicting fact explicit and never presents it as approved", () => {
    render(<StatusBadge value="conflict" />);
    expect(screen.getByText("存在冲突")).toHaveClass("badge-danger");
    expect(screen.queryByText("已批准")).not.toBeInTheDocument();
  });
  it("lets keyboard users skip repeated navigation without changing the route", () => {
    render(
      <WorkspaceShell
        user={{
          id: "user",
          tenant_id: "tenant",
          email: "preview@example.test",
          display_name: "Preview",
          role: "admin",
        }}
        activeWorkbench="research"
        activeView="explorer"
        onView={vi.fn()}
        onLogout={vi.fn()}
      >
        Content
      </WorkspaceShell>,
    );
    const before = window.location.href;
    fireEvent.click(screen.getByRole("button", { name: "跳到主要内容" }));
    expect(screen.getByRole("main")).toHaveFocus();
    expect(window.location.href).toBe(before);
  });

  it("adds quiet decorative state icons without duplicating accessible messages", () => {
    const { rerender } = render(<EmptyState title="暂无已发布记录" detail="请调整筛选" />);
    expect(screen.getByRole("status")).toHaveTextContent("暂无已发布记录请调整筛选");
    expect(document.querySelector(".state-icon svg")).toHaveAttribute("aria-hidden", "true");
    rerender(<ErrorState message="连接失败" retry={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("连接失败");
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });

  it("styles grouped review choices through the same authority as ungrouped choices", () => {
    const governance = style("governance.css");
    expect(governance).toContain(".review-list :where(button)");
    expect(governance).not.toContain(".review-list > button {");
    expect(governance).toContain(".review-list > details > summary");
  });

  it("does not let generic domain fields recreate borders inside composite entity controls", () => {
    const research = style("research.css");
    expect(research).toContain(".domain-filter-bar :where(input, select)");
    expect(research).not.toContain(".domain-filter-bar input {");
    expect(research).not.toContain(".domain-filter-bar input:focus {");
  });

  it("loads evidence/knowledge layouts only in their owners, including their responsive authority", () => {
    const rootPath = "../styles.css";
    const root = readFileSync(fileURLToPath(new URL(rootPath, import.meta.url)), "utf8");
    expect(root).not.toContain("styles/knowledge.css");
    for (const owner of ["KnowledgeView", "EvidenceView"]) {
      const path = `../views/${owner}.tsx`;
      expect(readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8")).toContain(
        'import "../styles/knowledge.css";',
      );
    }
    expect(style("knowledge.css")).toContain("@media (max-width: 760px)");
    expect(style("chemistry.css")).not.toContain(".knowledge-page-list");
  });

  it("removes the closed mobile drawer from focus/navigation and restores desktop access on resize", () => {
    const previous = Object.getOwnPropertyDescriptor(window, "matchMedia");
    let compact = true;
    const listeners = new Set<() => void>();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: () => ({
        get matches() {
          return compact;
        },
        addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
      }),
    });
    try {
      const { unmount } = render(
        <WorkspaceShell
          user={{
            id: "user",
            tenant_id: "tenant",
            email: "preview@example.test",
            display_name: "Preview",
            role: "admin",
          }}
          activeWorkbench="research"
          activeView="explorer"
          onView={vi.fn()}
          onLogout={vi.fn()}
        >
          Content
        </WorkspaceShell>,
      );
      const navigation = document.getElementById("workspace-navigation");
      expect(navigation).toHaveAttribute("inert");
      expect(navigation).toHaveAttribute("aria-hidden", "true");
      expect(screen.queryByRole("button", { name: "情报检索" })).not.toBeInTheDocument();
      const opener = screen.getByRole("button", { name: "打开导航" });
      fireEvent.click(opener);
      expect(navigation).not.toHaveAttribute("inert");
      expect(opener).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByRole("main").parentElement).toHaveAttribute("inert");
      act(() => {
        compact = false;
        for (const listener of listeners) listener();
      });
      expect(navigation).not.toHaveAttribute("aria-hidden");
      expect(opener).toHaveAttribute("aria-expanded", "false");
      expect(screen.getByRole("main").parentElement).not.toHaveAttribute("inert");
      unmount();
      expect(listeners.size).toBe(0);
    } finally {
      if (previous) Object.defineProperty(window, "matchMedia", previous);
      else Reflect.deleteProperty(window, "matchMedia");
    }
  });
});
