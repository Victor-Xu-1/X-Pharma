import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { researchWorkflowForView, researchWorkflows } from "../lib/workspace/researchNavigation";
import type { ViewKey } from "../lib/workspaceRouting";
import { canAccessView, workbenchForView } from "../lib/workspaceRouting";

const user = {
  id: "researcher",
  tenant_id: "organization",
  email: "researcher@example.test",
  display_name: "研发人员",
  role: "viewer" as const,
};

it("consolidates thirteen research destinations into five non-overlapping workflow entries", () => {
  const onView = vi.fn();
  render(
    <WorkspaceShell user={user} activeWorkbench="research" activeView="explorer" onView={onView} onLogout={vi.fn()}>
      research
    </WorkspaceShell>,
  );
  const navigation = screen.getByRole("navigation", { name: "主导航" });
  expect(
    within(navigation)
      .getAllByRole("button")
      .map((button) => button.textContent),
  ).toEqual(["情报检索", "研发数据", "竞争情报", "研究动态", "我的研究"]);
  for (const [label, view] of [
    ["情报检索", "explorer"],
    ["研发数据", "pipeline"],
    ["竞争情报", "patents"],
    ["研究动态", "news"],
    ["我的研究", "collections"],
  ]) {
    fireEvent.click(within(navigation).getByRole("button", { name: label }));
    expect(onView).toHaveBeenLastCalledWith(view);
  }
  expect(within(navigation).queryByRole("button", { name: "用户中心" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "环境管理" })).not.toBeInTheDocument();
});

it("keeps comparison, saved-search monitoring and knowledge as one workflow's page navigation", () => {
  const onView = vi.fn();
  render(
    <WorkspaceShell user={user} activeWorkbench="research" activeView="collections" onView={onView} onLogout={vi.fn()}>
      research
    </WorkspaceShell>,
  );
  const navigation = screen.getByRole("navigation", { name: "我的研究分类" });
  for (const [label, view] of [
    ["对比列表", "collections"],
    ["监控与提醒", "monitoring"],
    ["知识专题", "knowledge"],
  ]) {
    fireEvent.click(within(navigation).getByRole("button", { name: label }));
    if (view === "collections") expect(onView).not.toHaveBeenCalled();
    else expect(onView).toHaveBeenLastCalledWith(view);
  }
  expect(within(navigation).queryByRole("button", { name: "证据查证" })).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", { name: "我的研究" }),
  ).toHaveAttribute("aria-current", "page");
});

it("keeps environment management in the internal administrator boundary", () => {
  const environment = "environment" as Parameters<typeof canAccessView>[0];
  expect(workbenchForView(environment)).toBe("internal");
  expect(canAccessView(environment, "admin")).toBe(true);
  expect(canAccessView(environment, "analyst")).toBe(false);
  expect(canAccessView(environment, "viewer")).toBe(false);
});

it("assigns every original research destination exactly once without an extra hub route", () => {
  const destinations = researchWorkflows.flatMap((workflow) => workflow.destinations.map((item) => item.view));
  expect(new Set(destinations).size).toBe(13);
  expect(destinations).toHaveLength(13);
  expect(destinations.every((view) => workbenchForView(view) === "research")).toBe(true);
});

it.each(
  researchWorkflows.flatMap((workflow) => workflow.destinations.map((item) => [item.view, workflow.label] as const)),
)("retains %s deep links under the %s sidebar entry", (view, label) => {
  render(
    <WorkspaceShell user={user} activeWorkbench="research" activeView={view} onView={vi.fn()} onLogout={vi.fn()}>
      research
    </WorkspaceShell>,
  );
  const primary = screen.getByRole("navigation", { name: "主导航" });
  expect(within(primary).getAllByRole("button")).toHaveLength(5);
  expect(within(primary).getByRole("button", { name: label })).toHaveAttribute("aria-current", "page");
  if (view === "news") expect(document.querySelector(".research-view-navigation")).toBeNull();
  else
    expect(document.querySelector(".research-view-navigation [aria-current=page]")).toHaveTextContent(
      researchWorkflowForView(view)?.destinations.find((item) => item.view === view)?.label ?? "",
    );
});

it.each([
  ["drug", null, "研发数据"],
  ["target", "chemistry", "情报检索"],
  ["company", null, "竞争情报"],
  ["disease", "collections", "我的研究"],
  ["entity", null, "情报检索"],
  ["drug", "overview", "研发数据"],
] as const)("keeps %s dossier context from %s without stacking another category row", (view, source, label) => {
  render(
    <WorkspaceShell
      user={user}
      activeWorkbench="research"
      activeView={view}
      sourceView={source}
      onView={vi.fn()}
      onLogout={vi.fn()}
    >
      dossier
    </WorkspaceShell>,
  );
  expect(
    within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", { name: label }),
  ).toHaveAttribute("aria-current", "page");
  expect(document.querySelector(".research-view-navigation")).toBeNull();
});

it.each(["overview", "factory", "environment"] as ViewKey[])("does not claim %s as a research workflow", (view) => {
  expect(researchWorkflowForView(view)).toBeUndefined();
});

it.each(["trials", "patents", "deals", "regulatory", "news"] as ViewKey[])(
  "does not stack category navigation on a %s record dossier",
  (view) => {
    render(
      <WorkspaceShell
        user={user}
        activeWorkbench="research"
        activeView={view}
        researchDetail
        onView={vi.fn()}
        onLogout={vi.fn()}
      >
        record dossier
      </WorkspaceShell>,
    );
    expect(document.querySelector(".research-view-navigation")).toBeNull();
    expect(
      within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", {
        name: researchWorkflowForView(view)?.label,
      }),
    ).toHaveAttribute("aria-current", "page");
  },
);

it("keeps collapsed workflow labels accessible and does not duplicate the removed research sidebar", () => {
  render(
    <WorkspaceShell user={user} activeWorkbench="research" activeView="evidence" onView={vi.fn()} onLogout={vi.fn()}>
      evidence
    </WorkspaceShell>,
  );
  fireEvent.click(screen.getByRole("button", { name: "收起导航" }));
  for (const workflow of researchWorkflows) {
    expect(
      within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", { name: workflow.label }),
    ).toHaveAttribute("title", workflow.label);
  }
  expect(screen.queryByRole("navigation", { name: "我的研究" })).not.toBeInTheDocument();
});
