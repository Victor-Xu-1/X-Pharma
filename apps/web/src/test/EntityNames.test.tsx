import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EntityNames } from "../components/EntityNames";

it("omits empty name sections and canonical duplicates", () => {
  const { container } = render(<EntityNames entity={{ name: "Compound A", aliases: [" compound   a ", ""] }} />);
  expect(container).toBeEmptyDOMElement();
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
