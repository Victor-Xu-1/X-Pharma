import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadEnvironment, prepareEnvironmentPlan } from "../lib/contracts/environment";
import type { EnvironmentRead } from "../lib/generated";
import { EnvironmentView } from "../views/EnvironmentView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/environment", () => ({
  environmentKeys: { snapshot: ["environment", "snapshot"] },
  loadEnvironment: vi.fn(),
  prepareEnvironmentPlan: vi.fn(),
}));
const environment: EnvironmentRead = {
  generated_at: "2026-10-04T00:00:00Z",
  product_version: "0.1.0",
  environment: "development",
  host_status: "not_configured",
  host: null,
  host_detail: "尚未连接主机检测报告",
  runtime: [
    {
      id: "python",
      label: "Python",
      scope: "gateway",
      status: "present",
      observed: "3.13.14",
      expected: null,
      detail: "网关进程实际版本",
    },
  ],
  recipes: [
    {
      id: "frontend-dependencies",
      label: "前端依赖",
      description: "使用锁定包管理器",
      offline_supported: true,
      prerequisites: ["Node.js", "Corepack"],
    },
  ],
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadEnvironment).mockResolvedValue(environment);
});

it.each([null, "d".repeat(40)])(
  "shows the installation source separately from host detection: %s",
  async (revision) => {
    vi.mocked(loadEnvironment).mockResolvedValue({
      ...environment,
      host_status: "current",
      host: {
        generated_at: "2026-10-04T00:00:00Z",
        product_version: "0.1.0",
        revision: "a".repeat(40),
        clean_source: true,
        manifest_sha256: "b".repeat(64),
        probes: [],
        disk_free_bytes: 4 * 1024 ** 3,
        disk_total_bytes: 8 * 1024 ** 3,
        latest_install: {
          recipe_id: "frontend-dependencies",
          plan_id: "c".repeat(64),
          revision,
          status: "succeeded",
          started_at: "2026-10-03T00:00:00Z",
          detail: "Installation observed",
        },
      },
    });
    renderWithQueryClient(<EnvironmentView />);
    await screen.findByRole("table", { name: "主机依赖版本" });
    expect(screen.getByText(/最近安装/)).toHaveTextContent(
      revision ? "安装时源码 dddddddddddd" : "旧记录未绑定源码，不能作为当前源码的安装证明",
    );
  },
);

it("distinguishes gateway versions from absent host evidence and disables installation", async () => {
  renderWithQueryClient(<EnvironmentView />);
  await waitFor(() => expect(screen.getByRole("table", { name: "网关依赖版本" })).toHaveTextContent("3.13.14"));
  expect(screen.queryByRole("table", { name: "主机依赖版本" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "安装与修复" }));
  expect(screen.getByRole("button", { name: "生成安装计划" })).toBeDisabled();
  expect(prepareEnvironmentPlan).not.toHaveBeenCalled();
});

it("generates an offline-bound plan but never executes it in the browser", async () => {
  vi.mocked(loadEnvironment).mockResolvedValue({
    ...environment,
    host_status: "current",
    host: {
      generated_at: "2026-10-04T00:00:00Z",
      product_version: "0.1.0",
      revision: "a".repeat(40),
      clean_source: true,
      manifest_sha256: "b".repeat(64),
      probes: [],
      disk_free_bytes: 4 * 1024 ** 3,
      disk_total_bytes: 8 * 1024 ** 3,
      latest_install: null,
    },
  });
  vi.mocked(prepareEnvironmentPlan).mockResolvedValue({
    generated_at: "2026-10-04T00:00:00Z",
    expires_at: "2026-10-05T00:00:00Z",
    product_version: "0.1.0",
    revision: "a".repeat(40),
    manifest_sha256: "b".repeat(64),
    recipe_id: "frontend-dependencies",
    offline: true,
    commands: [["corepack", "pnpm@11.7.0", "--dir", "apps/web", "install", "--frozen-lockfile", "--offline"]],
    plan_id: "c".repeat(64),
  });
  renderWithQueryClient(<EnvironmentView />);
  await screen.findByRole("tab", { name: "安装与修复" });
  fireEvent.click(screen.getByRole("tab", { name: "安装与修复" }));
  fireEvent.click(screen.getByRole("button", { name: "生成安装计划" }));
  await screen.findByText("安装计划已生成，尚未执行");
  expect(prepareEnvironmentPlan).toHaveBeenCalledWith({ recipe_id: "frontend-dependencies", offline: true });
  expect(screen.getByRole("button", { name: "下载安装计划" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "立即安装" })).not.toBeInTheDocument();
});

it("shows a failed plan request without claiming installation success", async () => {
  vi.mocked(loadEnvironment).mockResolvedValue({
    ...environment,
    host_status: "current",
    host: {
      generated_at: "2026-10-04T00:00:00Z",
      product_version: "0.1.0",
      revision: "a".repeat(40),
      clean_source: true,
      manifest_sha256: "b".repeat(64),
      probes: [],
      disk_free_bytes: 4 * 1024 ** 3,
      disk_total_bytes: 8 * 1024 ** 3,
    },
  });
  vi.mocked(prepareEnvironmentPlan).mockRejectedValue(new Error("主机报告已过期"));
  renderWithQueryClient(<EnvironmentView />);
  await screen.findByRole("tab", { name: "安装与修复" });
  fireEvent.click(screen.getByRole("tab", { name: "安装与修复" }));
  fireEvent.click(screen.getByRole("button", { name: "生成安装计划" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("主机报告已过期");
  expect(screen.queryByText("安装计划已生成，尚未执行")).not.toBeInTheDocument();
});
