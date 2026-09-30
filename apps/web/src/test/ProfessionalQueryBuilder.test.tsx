import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfessionalQueryBuilder } from "../components/ProfessionalQueryBuilder";
import { loadPipelineFacetCatalog } from "../lib/contracts/pipeline";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/pipeline", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/pipeline")>();
  return {
    ...actual,
    loadPipelineFacetCatalog: vi.fn().mockResolvedValue({
      as_of: "2026-08-08T00:00:00Z",
      facets: {},
      warnings: [],
    }),
  };
});

describe("ProfessionalQueryBuilder", () => {
  it("does not turn empty governed catalogs into noisy public filters", async () => {
    renderWithQueryClient(<ProfessionalQueryBuilder query="SEC61G" onExecute={vi.fn()} />);

    await waitFor(() => expect(vi.mocked(loadPipelineFacetCatalog)).toHaveBeenCalledOnce());

    expect(document.querySelectorAll(".professional-facet-state")).toHaveLength(0);
    expect(document.body).not.toHaveTextContent(/暂无可用.*选项/);
  });
});
