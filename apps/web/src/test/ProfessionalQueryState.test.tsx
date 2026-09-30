import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ProfessionalQueryState, QueryRefreshButton, statusLabel } from "../components/common";
import { ApiError } from "../lib/api";

const baseProps = {
  dataAvailable: false,
  error: null,
  fallbackError: "查询失败",
  isCancelled: false,
  isFetching: false,
  loadingLabel: "正在查询专利族",
  onCancel: vi.fn(),
  onDismissCancellation: vi.fn(),
  onRetry: vi.fn(),
};

describe("professional query lifecycle", () => {
  it("translates operational status codes for human operators", () => {
    expect(statusLabel("passed")).toBe("通过");
    expect(statusLabel("ready_to_resolve")).toBe("待关闭");
    expect(statusLabel("recovered")).toBe("已恢复");
    expect(statusLabel("ready")).toBe("就绪");
    expect(statusLabel("partial")).toBe("部分完成");
    expect(statusLabel("medium")).toBe("中");
  });

  it("distinguishes an idle query from a user cancellation", () => {
    render(<ProfessionalQueryState {...baseProps} enabled={false} idle={<span>输入检索条件</span>} />);

    expect(screen.getByText("输入检索条件")).toBeVisible();
    expect(screen.queryByText("查询已取消")).not.toBeInTheDocument();
  });

  it("announces empty result states without treating them as errors", () => {
    render(<EmptyState title="未找到匹配实体" detail="请调整筛选条件" />);

    const state = screen.getByRole("status");
    expect(state).toHaveAttribute("aria-live", "polite");
    expect(state).toHaveAttribute("aria-atomic", "true");
    expect(state).toHaveTextContent("未找到匹配实体");
    expect(state).toHaveTextContent("请调整筛选条件");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers cancellation during the initial request", () => {
    const onCancel = vi.fn();
    render(<ProfessionalQueryState {...baseProps} isFetching onCancel={onCancel} />);

    fireEvent.click(screen.getByRole("button", { name: "取消查询" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("preserves successful data while refreshing or recovering from a transient failure", () => {
    const { rerender } = render(
      <ProfessionalQueryState {...baseProps} dataAvailable isFetching>
        <table aria-label="专业结果" />
      </ProfessionalQueryState>,
    );
    expect(screen.getByRole("table", { name: "专业结果" })).toBeVisible();
    expect(screen.getByText("正在刷新查询专利族")).toBeVisible();

    rerender(
      <ProfessionalQueryState {...baseProps} dataAvailable error={new ApiError("上游暂不可用", 503, "request-1")}>
        <table aria-label="专业结果" />
      </ProfessionalQueryState>,
    );
    expect(screen.getByText(/当前仍显示上次成功结果/)).toBeVisible();
    expect(screen.getByRole("table", { name: "专业结果" })).toBeVisible();
  });

  it("fails closed and hides retained data after an authorization denial", () => {
    render(
      <ProfessionalQueryState {...baseProps} dataAvailable error={new ApiError("Forbidden", 403, "request-2")}>
        <table aria-label="受限结果" />
      </ProfessionalQueryState>,
    );

    expect(screen.getByText("当前账号无权读取这组结果")).toBeVisible();
    expect(screen.queryByRole("table", { name: "受限结果" })).not.toBeInTheDocument();
  });

  it("keeps filters and prior data after a refresh cancellation", () => {
    const onRetry = vi.fn();
    const onDismissCancellation = vi.fn();
    render(
      <ProfessionalQueryState
        {...baseProps}
        dataAvailable
        isCancelled
        onRetry={onRetry}
        onDismissCancellation={onDismissCancellation}
      >
        <table aria-label="保留结果" />
      </ProfessionalQueryState>,
    );

    expect(screen.getByText("刷新已取消")).toBeVisible();
    expect(screen.getByRole("table", { name: "保留结果" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "重新刷新" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(onDismissCancellation).toHaveBeenCalledOnce();
  });

  it("exposes an explicit refresh command", () => {
    const onRefresh = vi.fn();
    render(<QueryRefreshButton refreshing={false} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole("button", { name: "刷新当前结果" }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });
});
