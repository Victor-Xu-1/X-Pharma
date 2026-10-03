import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { canAccessView, workbenchForView } from "../lib/workspaceRouting";

const user = {
  id: "researcher",
  tenant_id: "organization",
  email: "researcher@example.test",
  display_name: "研发人员",
  role: "viewer" as const,
};

it("makes existing saved-search monitoring, knowledge and comparison workflows discoverable", () => {
  const onView = vi.fn();
  render(
    <WorkspaceShell user={user} activeWorkbench="research" activeView="explorer" onView={onView} onLogout={vi.fn()}>
      research
    </WorkspaceShell>,
  );
  const navigation = screen.getByRole("navigation", { name: "我的研究" });
  for (const [label, view] of [
    ["对比列表", "collections"],
    ["监控与提醒", "monitoring"],
    ["知识专题", "knowledge"],
    ["证据查证", "evidence"],
  ]) {
    fireEvent.click(within(navigation).getByRole("button", { name: label }));
    expect(onView).toHaveBeenLastCalledWith(view);
  }
  expect(within(navigation).queryByRole("button", { name: "用户中心" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "环境管理" })).not.toBeInTheDocument();
});

it("keeps environment management in the internal administrator boundary", () => {
  const environment = "environment" as Parameters<typeof canAccessView>[0];
  expect(workbenchForView(environment)).toBe("internal");
  expect(canAccessView(environment, "admin")).toBe(true);
  expect(canAccessView(environment, "analyst")).toBe(false);
  expect(canAccessView(environment, "viewer")).toBe(false);
});
