import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";

import { ResearchTabList } from "../components/ResearchTabList";

const tabs = [
  { key: "overview", label: "概览" },
  { key: "evidence", label: "证据" },
  { key: "patents", label: "专利" },
] as const;

it("links alternate views to an explicitly shared panel without changing stable tab identifiers", () => {
  render(
    <ResearchTabList
      tabs={tabs.map((tab) => ({ ...tab, panelId: "shared-research-panel" }))}
      activeTab="overview"
      onChange={vi.fn()}
      ariaLabel="共享研究分区"
      idPrefix="shared-research"
    />,
  );
  for (const tab of screen.getAllByRole("tab")) {
    expect(tab).toHaveAttribute("aria-controls", "shared-research-panel");
    expect(tab.id).toBe(`shared-research-tab-${tab.dataset.tabKey}`);
  }
});

function Harness({ onChange }: { onChange: (tab: (typeof tabs)[number]["key"]) => void }) {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("overview");
  return (
    <ResearchTabList
      tabs={tabs}
      activeTab={activeTab}
      onChange={(tab) => {
        setActiveTab(tab);
        onChange(tab);
      }}
      ariaLabel="研究分区"
      idPrefix="research"
    />
  );
}

it("exposes a linked ARIA tab contract and supports roving keyboard navigation", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);

  const overview = screen.getByRole("tab", { name: "概览" });
  const evidence = screen.getByRole("tab", { name: "证据" });
  const patents = screen.getByRole("tab", { name: "专利" });
  expect(overview).toHaveAttribute("aria-controls", "research-panel-overview");
  expect(overview).toHaveAttribute("aria-selected", "true");
  expect(evidence).toHaveAttribute("tabindex", "-1");

  overview.focus();
  fireEvent.keyDown(overview, { key: "ArrowRight" });
  expect(evidence).toHaveFocus();
  expect(evidence).toHaveAttribute("aria-selected", "true");
  expect(onChange).toHaveBeenLastCalledWith("evidence");

  fireEvent.keyDown(evidence, { key: "End" });
  expect(patents).toHaveFocus();
  expect(onChange).toHaveBeenLastCalledWith("patents");

  fireEvent.keyDown(patents, { key: "ArrowRight" });
  expect(overview).toHaveFocus();
  expect(onChange).toHaveBeenLastCalledWith("overview");
});

it("scrolls the active tab into view when a deep link opens a later section", () => {
  const scrollIntoView = vi.fn();
  const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: scrollIntoView,
  });

  try {
    render(
      <ResearchTabList tabs={tabs} activeTab="patents" onChange={vi.fn()} ariaLabel="研究分区" idPrefix="research" />,
    );
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest", inline: "nearest" });
  } finally {
    if (originalScrollIntoView) {
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
        configurable: true,
        value: originalScrollIntoView,
      });
    } else {
      delete (HTMLElement.prototype as { scrollIntoView?: unknown }).scrollIntoView;
    }
  }
});

it("shows record counts and skips sections that are known to be empty", () => {
  const onChange = vi.fn();
  const availabilityTabs = [
    { key: "overview", label: "概览" },
    { key: "evidence", label: "证据", count: 0, disabled: true, disabledReason: "暂无证据" },
    { key: "patents", label: "专利", count: 2 },
  ] as const;

  render(
    <ResearchTabList
      tabs={availabilityTabs}
      activeTab="overview"
      onChange={onChange}
      ariaLabel="研究分区"
      idPrefix="availability"
    />,
  );

  const overview = screen.getByRole("tab", { name: "概览" });
  const evidence = screen.getByRole("tab", { name: "证据（0）" });
  const patents = screen.getByRole("tab", { name: "专利（2）" });
  expect(evidence).toHaveAttribute("aria-disabled", "true");
  expect(evidence).toHaveAttribute("title", "暂无证据");

  fireEvent.click(evidence);
  expect(onChange).not.toHaveBeenCalled();

  overview.focus();
  fireEvent.keyDown(overview, { key: "ArrowRight" });
  expect(patents).toHaveFocus();
  expect(onChange).toHaveBeenCalledWith("patents");
});
