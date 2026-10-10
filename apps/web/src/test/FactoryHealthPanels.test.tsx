import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { setLocale } from "../lib/i18n";
import { FactoryDetailsPanel } from "../views/dataFactory/FactoryDetailsPanel";
import { SearchProjectionPanel } from "../views/dataFactory/SearchProjectionPanel";

const status = {
  available: true,
  cluster_name: "Original cluster",
  cluster_status: "yellow",
  version: "3.6.0",
  aliases: { source_alias: ["source_index"] },
  deliveries: { pending: 0, failed: 0, dead: 0 },
  error: null,
};

it("preserves a deliberately opened details panel when a revealed problem recovers", () => {
  const view = render(
    <FactoryDetailsPanel title="State" summary="Problem" reveal>
      Body
    </FactoryDetailsPanel>,
  );
  const details = screen.getByText("Body").closest("details");
  expect(details).toHaveAttribute("open");
  view.rerender(
    <FactoryDetailsPanel title="State" summary="Recovered">
      Body
    </FactoryDetailsPanel>,
  );
  expect(details).toHaveAttribute("open");
});

it("renders English projection status and switches framing without translating source-owned cluster fields", () => {
  setLocale("en");
  render(<SearchProjectionPanel data={status} pending={false} error={null} onRetry={vi.fn()} />);
  expect(screen.getByRole("heading", { name: "Search projection status" })).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  fireEvent.click(screen.getByText("检索投影运行状态"));
  expect(screen.getByText("Original cluster")).toBeInTheDocument();
  expect(screen.getByText("yellow")).toBeInTheDocument();
});

it("does not expose previously cached cluster facts after the projection request loses permission", () => {
  setLocale("en");
  render(
    <SearchProjectionPanel
      data={status}
      pending={false}
      error={new ApiError("RAW_PROJECTION_DENIAL", 403, null)}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getByText("RAW_PROJECTION_DENIAL")).toBeVisible();
  expect(screen.queryByText("Original cluster")).not.toBeInTheDocument();
});

it("does not label an unobserved or loading projection as connectable", () => {
  setLocale("en");
  const view = render(<SearchProjectionPanel data={undefined} pending error={null} onRetry={vi.fn()} />);
  expect(screen.queryByText("Connectable")).not.toBeInTheDocument();
  view.rerender(<SearchProjectionPanel data={undefined} pending={false} error={null} onRetry={vi.fn()} />);
  expect(screen.getByText("Not observed")).toBeInTheDocument();
});
