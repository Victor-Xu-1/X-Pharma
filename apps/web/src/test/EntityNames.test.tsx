import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EntityNames } from "../components/EntityNames";
import { setLocale } from "../lib/i18n";

it("omits empty name sections and canonical duplicates", () => {
  const { container } = render(<EntityNames entity={{ name: "Compound A", aliases: [" compound   a ", ""] }} />);
  expect(container).toBeEmptyDOMElement();
});

it("switches alias labels in place without collapsing source-reported names", () => {
  const entity = {
    name: "中文药物",
    aliases: ["CODE-1", "CODE-2", "CODE-3", "CODE-4", "CODE-5", "CODE-6", "中文代号"],
  };
  const { rerender } = render(<EntityNames entity={entity} />);
  fireEvent.click(screen.getByText("更多别名（1）"));
  setLocale("en");
  rerender(<EntityNames entity={entity} />);
  expect(screen.getByRole("region", { name: "Aliases and development codes" })).toBeVisible();
  expect(screen.getByText("More aliases (1)")).toBeVisible();
  expect(screen.getByText("中文代号")).toBeVisible();
});

it("keeps a compact first view while retaining every source-reported name", () => {
  render(
    <EntityNames
      entity={{
        name: "Compound A",
        aliases: ["CODE-1", " code-1 ", "CODE-2", "CODE-3", "CODE-4", "CODE-5", "CODE-6", "CODE-7"],
      }}
    />,
  );
  expect(screen.getAllByText("CODE-1")).toHaveLength(1);
  expect(screen.getByText("CODE-7")).not.toBeVisible();
  const summary = screen.getByText("更多别名（1）");
  fireEvent.click(summary);
  expect(screen.getByText("CODE-7")).toBeVisible();
});
