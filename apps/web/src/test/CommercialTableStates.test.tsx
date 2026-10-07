import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { BillingDisputeTable } from "../views/commercial/BillingDisputeTable";
import { BillingOperations } from "../views/commercial/BillingOperations";
import { ClientTable } from "../views/commercial/ClientTable";

it("keeps an empty client message outside a wide, horizontally scrolled table", () => {
  render(<ClientTable items={[]} busy="" onAction={vi.fn()} />);
  expect(screen.getByRole("status")).toHaveTextContent("暂无 Agent 客户端");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("keeps dispute filtering usable when no cases exist without creating an empty wide table", () => {
  const onFilter = vi.fn();
  render(<BillingDisputeTable items={[]} filter="all" busy="" onFilter={onFilter} onAction={vi.fn()} />);
  fireEvent.change(screen.getByRole("combobox", { name: "争议状态" }), { target: { value: "open" } });
  expect(onFilter).toHaveBeenCalledExactlyOnceWith("open");
  expect(screen.getByRole("status")).toHaveTextContent("暂无计费争议");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("shows each empty billing state inside its own section with no off-screen colspan placeholders", () => {
  render(
    <BillingOperations
      accounts={[]}
      deliveries={[]}
      deliveryFilter="all"
      busy=""
      onDeliveryFilter={vi.fn()}
      onMapping={vi.fn()}
      onReplay={vi.fn()}
      onDispute={vi.fn()}
    />,
  );
  expect(within(screen.getByRole("region", { name: "计费账户映射" })).getByRole("status")).toHaveTextContent(
    "暂无计费账户",
  );
  expect(within(screen.getByRole("region", { name: "Provider 投递队列" })).getByRole("status")).toHaveTextContent(
    "暂无账单投递记录",
  );
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
