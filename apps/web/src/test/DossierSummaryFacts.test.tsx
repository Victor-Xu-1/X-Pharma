import { fireEvent, render, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { DossierSummaryFacts } from "../views/dossier/DossierSummaryFacts";

const facts = {
  moreLabel: "More source facts",
  primary: [
    { key: "phase", label: "Phase", value: "SOURCE_FUTURE_PHASE" },
    { key: "programs", label: "Programs / drugs", value: "0 / 0" },
    { key: "targets", label: "Targets / conditions", value: 0 },
  ],
  secondary: [
    { key: "activity", label: "Last activity", value: "--" },
    { key: "source", label: "Raw source", value: "原始数据 / 0.00000012345" },
    { key: "count", label: "Count", value: "99999999999999999999999" },
  ],
} as const;

it("retains all six facts, unknown phase codes, zero counts, missing dates and raw precision", () => {
  const { container } = render(<DossierSummaryFacts {...facts} />);
  const primary = container.querySelector(".dossier-summary-primary");
  const secondary = container.querySelector(".dossier-summary-secondary");
  expect(primary?.children).toHaveLength(3);
  expect(secondary?.children).toHaveLength(3);
  expect(primary).toHaveTextContent("SOURCE_FUTURE_PHASE");
  expect(primary).toHaveTextContent("0 / 0");
  expect(secondary).toHaveTextContent("--");
  expect(secondary).toHaveTextContent("原始数据 / 0.00000012345");
  expect(secondary).toHaveTextContent("99999999999999999999999");
});

it("keeps an opened disclosure across caption updates and closes it for a different entity key", () => {
  const { container, rerender } = render(<DossierSummaryFacts key="entity-1" {...facts} />);
  const disclosure = container.querySelector("details") as HTMLDetailsElement;
  fireEvent.click(within(disclosure).getByText(facts.moreLabel));
  expect(disclosure).toHaveAttribute("open");
  rerender(<DossierSummaryFacts key="entity-1" {...facts} moreLabel="更多来源指标" />);
  expect(disclosure).toHaveAttribute("open");
  rerender(<DossierSummaryFacts key="entity-2" {...facts} />);
  expect(container.querySelector("details")).not.toHaveAttribute("open");
});
