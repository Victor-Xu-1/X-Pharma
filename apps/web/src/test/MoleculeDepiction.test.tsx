import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { MoleculeDepiction } from "../components/MoleculeDepiction";
import { setLocale } from "../lib/i18n";
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

it("updates the structure image caption without rerendering chemistry or changing its source", async () => {
  vi.mocked(renderMolecule).mockResolvedValue({
    svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    version: "SOURCE_VERSION",
  });
  setLocale("en");
  render(<MoleculeDepiction smiles="F[C@H](Cl)Br" name="原始名称" />);
  const original = await screen.findByRole("img", { name: "2D structure of 原始名称" });
  const src = original.getAttribute("src");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("img", { name: "原始名称 2D 结构" })).toHaveAttribute("src", src);
  expect(renderMolecule).toHaveBeenCalledExactlyOnceWith("F[C@H](Cl)Br");
});
