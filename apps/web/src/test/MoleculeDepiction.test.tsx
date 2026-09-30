import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { MoleculeDepiction } from "../components/MoleculeDepiction";
import { renderMolecule } from "../lib/rdkitRenderer";

vi.mock("../lib/rdkitRenderer", () => ({
  renderMolecule: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(renderMolecule).mockReset();
});

it("renders the worker result and publishes its RDKit version", async () => {
  vi.mocked(renderMolecule).mockResolvedValue({
    svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    version: "2025.03.4",
  });
  const { container } = render(<MoleculeDepiction smiles="CCO" name="Ethanol" />);

  const figure = container.querySelector(".molecule-depiction");
  await waitFor(() => expect(figure).toHaveAttribute("data-rdkit-version", "2025.03.4"));
  const image = container.querySelector("img");
  expect(image?.getAttribute("src")).toContain("data:image/svg+xml");
});

it("shows the bounded fallback when rendering fails", async () => {
  vi.mocked(renderMolecule).mockRejectedValue(new Error("worker unavailable"));
  const { container } = render(<MoleculeDepiction smiles="CCO" name="Ethanol" />);

  await waitFor(() => expect(container.querySelector(".molecule-fallback")).toBeInTheDocument());
  expect(container.querySelector(".molecule-loading")).not.toBeInTheDocument();
});
