import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { setLocale } from "../lib/i18n";
import { PRODUCT_RELEASE } from "../lib/product";

it.each(["research", "internal"] as const)(
  "marks every controlled %s primary label for readable wrapping",
  (workbench) => {
    setLocale("en");
    render(
      <WorkspaceShell
        user={{
          id: "admin",
          tenant_id: "tenant",
          email: "admin@example.test",
          display_name: "原始用户名字",
          role: "admin",
        }}
        activeWorkbench={workbench}
        activeView={workbench === "research" ? "overview" : "factory"}
        onView={vi.fn()}
        onLogout={vi.fn()}
      >
        workspace
      </WorkspaceShell>,
    );
    const primary = screen.getByRole("navigation", { name: "Primary navigation" });
    const buttons = within(primary).getAllByRole("button");
    expect(buttons).toHaveLength(5);
    for (const button of buttons) expect(button.querySelector("span")).toHaveClass("sidebar-nav-label");
    expect(
      within(primary).getByRole("button", {
        name: workbench === "research" ? "Competitive intelligence" : "Environment management",
      }),
    ).toHaveTextContent(workbench === "research" ? "Competitive intelligence" : "Environment management");
    if (workbench === "internal") expect(screen.getByText("原始用户名字")).not.toHaveClass("sidebar-nav-label");
  },
);

it.each(["research", "internal"] as const)(
  "keeps the %s account actions together without an invented online status",
  (workbench) => {
    render(
      <WorkspaceShell
        user={{ id: "admin", tenant_id: "tenant", email: "admin@example.test", display_name: "Admin", role: "admin" }}
        activeWorkbench={workbench}
        activeView={workbench === "research" ? "explorer" : "factory"}
        onView={vi.fn()}
        onLogout={vi.fn()}
      >
        workspace
      </WorkspaceShell>,
    );
    const accountNavigation = screen.getByRole("navigation", { name: "账户导航" });
    expect(screen.getByLabelText("工作台导航").lastElementChild).toBe(accountNavigation);
    expect(within(accountNavigation).getByRole("button", { name: "退出账号" })).toBeInTheDocument();
    expect(within(accountNavigation).getByRole("button", { name: "收起导航" })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "在线" })).not.toBeInTheDocument();
    expect(document.querySelector(".page-heading .eyebrow")).toBeNull();
  },
);

it("does not let a closing mobile navigation drawer steal focus from the destination heading", () => {
  const frames = new Map<number, FrameRequestCallback>();
  let nextFrame = 0;
  const requestFrame = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    const id = ++nextFrame;
    frames.set(id, callback);
    return id;
  });
  const cancelFrame = vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
    frames.delete(id);
  });
  const props = {
    user: {
      id: "user",
      tenant_id: "tenant",
      email: "user@example.test",
      display_name: "User",
      role: "analyst" as const,
    },
    activeWorkbench: "research" as const,
    onView: vi.fn(),
    onLogout: vi.fn(),
  };
  try {
    const { rerender } = render(
      <WorkspaceShell {...props} activeView="explorer">
        workspace
      </WorkspaceShell>,
    );
    const opener = screen.getByRole("button", { name: "打开导航" });
    opener.focus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "研发数据" }));
    rerender(
      <WorkspaceShell {...props} activeView="pipeline">
        workspace
      </WorkspaceShell>,
    );
    act(() => {
      for (const [id, callback] of frames) {
        frames.delete(id);
        callback(0);
      }
    });
    expect(screen.getByRole("heading", { name: "药物与研发管线" })).toHaveFocus();
  } finally {
    requestFrame.mockRestore();
    cancelFrame.mockRestore();
  }
});

it.each(["research", "internal"] as const)("uses the same supplied logo in the %s sidebar", (workbench) => {
  render(
    <WorkspaceShell
      user={{ id: "admin", tenant_id: "tenant", email: "admin@example.test", display_name: "Admin", role: "admin" }}
      activeWorkbench={workbench}
      activeView={workbench === "research" ? "explorer" : "factory"}
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );
  const mark = document.querySelector(".brand-symbol");
  expect(mark?.querySelector("img")).toHaveAttribute("src", expect.stringContaining("X-Pharma-logo-128.png"));
  expect(mark?.querySelector("svg")).toBeNull();
  expect(screen.getByText("X-Pharma")).toBeInTheDocument();
  expect(screen.getByText(PRODUCT_RELEASE)).toBeInTheDocument();
});

it("keeps the external workbench focused while retaining progressive access to specialist databases", () => {
  render(
    <WorkspaceShell
      user={{
        id: "analyst-1",
        tenant_id: "tenant-1",
        email: "analyst@example.test",
        display_name: "Analyst",
        role: "analyst",
      }}
      activeWorkbench="research"
      activeView="overview"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("button", { name: "情报检索" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "研发数据" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "情报总览" })).not.toBeInTheDocument();
  const accountNavigation = screen.getByRole("navigation", { name: "账户导航" });
  expect(within(accountNavigation).getByRole("button", { name: "用户中心" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByLabelText("工作台导航").lastElementChild).toBe(accountNavigation);
  const collapseButton = within(accountNavigation).getByRole("button", { name: "收起导航" });
  expect(accountNavigation.querySelector(".sidebar-account-row")?.lastElementChild).toBe(collapseButton);
  expect(within(accountNavigation).queryByText("收起导航")).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("navigation", { name: "主导航" })).queryByRole("button", { name: "用户中心" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "结构检索" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "专利情报" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "专业数据库" })).not.toBeInTheDocument();
  expect(screen.queryByText("核心查询")).not.toBeInTheDocument();
  const primaryNavigation = screen.getByRole("navigation", { name: "主导航" });
  for (const label of ["情报检索", "研发数据", "竞争情报", "研究动态", "我的研究"]) {
    expect(screen.getByRole("button", { name: label }).parentElement).toBe(primaryNavigation);
  }

  expect(screen.queryByRole("button", { name: "我的工作" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "原始证据" })).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "我的研究" })).not.toBeInTheDocument();
  expect(document.querySelector(".research-view-navigation")).toBeNull();
  expect(screen.queryByLabelText("外部情报工作台")).not.toBeInTheDocument();
  expect(screen.queryByText("医药情报平台")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("全局搜索")).not.toBeInTheDocument();
  expect(screen.queryByText("内部管理平台")).not.toBeInTheDocument();
  expect(screen.queryByText("数据工厂")).not.toBeInTheDocument();
  expect(screen.queryByText("Agent Gateway")).not.toBeInTheDocument();
  expect(screen.queryByText("MCP 独立授权")).not.toBeInTheDocument();
  expect(screen.queryByText("Information Workspace")).not.toBeInTheDocument();
  expect(screen.queryByText("analyst")).not.toBeInTheDocument();
  expect(screen.queryByText("INTELLIGENCE OVERVIEW")).not.toBeInTheDocument();
  expect(screen.queryByText("研究报告")).not.toBeInTheDocument();
  expect(screen.queryByText("研究包与演示文稿")).not.toBeInTheDocument();
  const topbar = screen.getByRole("banner");
  expect(within(topbar).queryByRole("button", { name: "退出登录" })).not.toBeInTheDocument();
  expect(within(topbar).queryByText("Analyst")).not.toBeInTheDocument();

  fireEvent.click(collapseButton);
  expect(screen.getByRole("button", { name: "展开导航" })).toBeInTheDocument();
  expect(document.querySelector(".workspace-shell")).toHaveClass("sidebar-collapsed");
});

it("marks the active specialist category and its parent workflow separately", () => {
  render(
    <WorkspaceShell
      user={{
        id: "analyst-1",
        tenant_id: "tenant-1",
        email: "analyst@example.test",
        display_name: "Analyst",
        role: "analyst",
      }}
      activeWorkbench="research"
      activeView="chemistry"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.queryByRole("button", { name: "专业数据库" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "结构检索" })).toHaveClass("active");
  expect(screen.getByRole("button", { name: "结构检索" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("button", { name: "情报检索" })).toHaveAttribute("aria-current", "page");
});

it("uses novice-facing copy for the comparison workspace", () => {
  render(
    <WorkspaceShell
      user={{
        id: "viewer-1",
        tenant_id: "tenant-1",
        email: "viewer@example.test",
        display_name: "Viewer",
        role: "viewer",
      }}
      activeWorkbench="research"
      activeView="collections"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("heading", { name: "对比列表", level: 1 })).toBeInTheDocument();
  expect(screen.queryByText("企业对比与列表")).not.toBeInTheDocument();
  expect(screen.queryByText("COMPARISON WORKSPACE")).not.toBeInTheDocument();
});

it("announces the active route and moves focus to the new page heading", () => {
  const { rerender } = render(
    <WorkspaceShell
      user={{
        id: "analyst-1",
        tenant_id: "tenant-1",
        email: "analyst@example.test",
        display_name: "Analyst",
        role: "analyst",
      }}
      activeWorkbench="research"
      activeView="overview"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("button", { name: "用户中心" })).toHaveAttribute("aria-current", "page");
  rerender(
    <WorkspaceShell
      user={{
        id: "analyst-1",
        tenant_id: "tenant-1",
        email: "analyst@example.test",
        display_name: "Analyst",
        role: "analyst",
      }}
      activeWorkbench="research"
      activeView="explorer"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("button", { name: "情报检索" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("button", { name: "用户中心" })).not.toHaveAttribute("aria-current");
  const pageHeading = screen.getByRole("heading", { name: "全局情报检索" });
  expect(pageHeading).toHaveFocus();
  expect(pageHeading).toHaveStyle({ outline: "none" });
});

it("does not advertise workspaces outside a viewer role", () => {
  render(
    <WorkspaceShell
      user={{
        id: "viewer-1",
        tenant_id: "tenant-1",
        email: "viewer@example.test",
        display_name: "Viewer",
        role: "viewer",
      }}
      activeWorkbench="research"
      activeView="overview"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("button", { name: "情报检索" })).toBeInTheDocument();
  expect(screen.queryByText("内部管理平台")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "数据工厂" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "AI 审核" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "商业运营" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "企业管理" })).not.toBeInTheDocument();
});

it("shows only governed operational navigation in the internal workbench", () => {
  const onLogout = vi.fn();

  render(
    <WorkspaceShell
      user={{
        id: "admin-1",
        tenant_id: "tenant-1",
        email: "admin@example.test",
        display_name: "Admin",
        role: "admin",
      }}
      activeWorkbench="internal"
      activeView="factory"
      onView={vi.fn()}
      onLogout={onLogout}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  expect(screen.getByRole("button", { name: "数据工厂" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "企业管理" })).toBeInTheDocument();
  expect(screen.getAllByText("内部管理工作台", { exact: true })).toHaveLength(1);
  expect(screen.queryByLabelText("内部管理工作台")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "环境管理" })).toBeInTheDocument();
  expect(screen.queryByText("医药情报平台")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "情报检索" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("全局搜索")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "退出账号" }));
  expect(onLogout).toHaveBeenCalledOnce();
});

it("moves focus into the mobile navigation and restores it after closing", async () => {
  render(
    <WorkspaceShell
      user={{
        id: "admin-1",
        tenant_id: "tenant-1",
        email: "admin@example.test",
        display_name: "Admin",
        role: "admin",
      }}
      activeWorkbench="internal"
      activeView="factory"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      <div>workspace</div>
    </WorkspaceShell>,
  );

  const openNavigation = screen.getByRole("button", { name: "打开导航" });
  openNavigation.focus();
  fireEvent.click(openNavigation);

  const mobileNavigation = screen.getByRole("complementary", { name: "工作台导航" });
  expect(mobileNavigation).toHaveClass("mobile-open");
  expect(openNavigation.closest(".workspace-main")).toHaveAttribute("inert");
  expect(screen.getByRole("button", { name: "跳到主要内容" })).toHaveAttribute("inert");
  expect(document.querySelector(".sidebar-scrim")).not.toHaveAttribute("inert");
  await waitFor(() => expect(within(mobileNavigation).getByRole("button", { name: "关闭导航" })).toHaveFocus());

  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(mobileNavigation).not.toHaveClass("mobile-open"));
  await waitFor(() => expect(openNavigation).toHaveFocus());
  expect(openNavigation.closest(".workspace-main")).not.toHaveAttribute("inert");
  expect(screen.getByRole("button", { name: "跳到主要内容" })).not.toHaveAttribute("inert");
  fireEvent.click(openNavigation);
  fireEvent.click(document.querySelector(".sidebar-scrim") as HTMLButtonElement);
  await waitFor(() => expect(openNavigation).toHaveFocus());
  expect(openNavigation.closest(".workspace-main")).not.toHaveAttribute("inert");
});
it("uses the same concise enterprise title as its navigation in English and Chinese", () => {
  setLocale("en");
  render(
    <WorkspaceShell
      user={{
        id: "admin",
        tenant_id: "tenant",
        email: "admin@example.test",
        display_name: "Original name",
        role: "admin",
      }}
      activeWorkbench="internal"
      activeView="enterprise"
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      workspace
    </WorkspaceShell>,
  );
  expect(screen.getByRole("heading", { name: "Enterprise management" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "zh-CN" } });
  expect(screen.getByRole("heading", { name: "企业管理" })).toBeInTheDocument();
  expect(screen.queryByText("企业账户与审计")).not.toBeInTheDocument();
});
