import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadDiseaseDossier } from "../lib/contracts/disease";
import { setLocale } from "../lib/i18n";
import { DiseaseView } from "../views/DiseaseView";
import { disease, dossier } from "./fixtures/diseaseDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/disease", () => ({
  diseaseKeys: { dossier: (id: string) => ["disease-dossier", id] },
  loadDiseaseDossier: vi.fn(),
}));
const props = {
  disease,
  activeSection: "overview" as const,
  onSectionChange: vi.fn(),
  onOpenEpidemiology: vi.fn(),
  onOpenEntity: vi.fn(),
  onOpenTrial: vi.fn(),
  onOpenPatent: vi.fn(),
  onOpenDeal: vi.fn(),
  onOpenRegulatoryEvent: vi.fn(),
  onOpenNewsEvent: vi.fn(),
};
beforeEach(() => {
  vi.clearAllMocks();
  setLocale("en");
  vi.mocked(loadDiseaseDossier).mockResolvedValue(dossier);
});

it("localizes disease captions without rewriting the source identity or repeating dossier reads", async () => {
  renderWithQueryClient(<DiseaseView {...props} />);
  await screen.findByRole("tablist", { name: "Disease dossier sections" });
  expect(screen.getByRole("heading", { name: disease.name })).toBeInTheDocument();
  expect(screen.getByText(disease.description as string)).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Latest disease burden observations" })).toBeInTheDocument();
  const reads = vi.mocked(loadDiseaseDossier).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("tablist", { name: "疾病专业档案视图" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: disease.name })).toBeInTheDocument();
  expect(loadDiseaseDossier).toHaveBeenCalledTimes(reads);
});

it("retains tiny values, zero sample sizes and partial reported bounds without inventing confidence levels", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValue({
    ...dossier,
    epidemiology: {
      ...dossier.epidemiology,
      items: [
        {
          ...dossier.epidemiology.items[0],
          value: 0.00000012345,
          lower_bound: 0,
          upper_bound: null,
          sample_size: 0,
          methodology: "原始方法 <source>",
        },
      ],
    },
  });
  renderWithQueryClient(<DiseaseView {...props} activeSection="epidemiology" />);
  const table = await screen.findByRole("table", { name: "Disease epidemiology observations" });
  expect(table).toHaveTextContent("0.00000012345");
  expect(table).toHaveTextContent("Reported bounds: 0 – --");
  expect(table).toHaveTextContent("Sample size: 0");
  expect(table).toHaveTextContent("原始方法 <source>");
  expect(table).not.toHaveTextContent("95%");
});

it("retains study tissue and variants beside source effect values and zeros", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValue({
    ...dossier,
    target_evidence: [
      {
        ...dossier.target_evidence[0],
        tissue: "原始组织",
        variant: "RAW_VARIANT",
        effect_size: 0,
        p_value: 0,
        sample_size: 0,
      },
    ],
  });
  renderWithQueryClient(<DiseaseView {...props} activeSection="evidence" />);
  const table = await screen.findByRole("table", { name: "Disease-linked target evidence" });
  expect(table).toHaveTextContent("原始组织");
  expect(table).toHaveTextContent("RAW_VARIANT");
  expect(table).toHaveTextContent("p=0 · n=0");
  expect(table).toHaveTextContent(dossier.target_evidence[0].summary);
});

it("exposes every loaded target beyond the ten-item overview without changing the opened disclosure on locale switch", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValue({
    ...dossier,
    target_evidence: Array.from({ length: 12 }, (_, index) => ({
      ...dossier.target_evidence[0],
      id: `e-${index}`,
      target_entity_id: `t-${index}`,
      target_name: `SOURCE_TARGET_${index}`,
    })),
  });
  const onOpenTarget = vi.fn();
  renderWithQueryClient(<DiseaseView {...props} onOpenTarget={onOpenTarget} />);
  const summary = await screen.findByText("More linked targets (3)");
  fireEvent.click(summary);
  const disclosure = summary.closest("details");
  if (!disclosure) throw new Error("Native target disclosure missing");
  fireEvent.click(within(disclosure).getByRole("button", { name: "SOURCE_TARGET_11" }));
  expect(onOpenTarget).toHaveBeenCalledWith("t-11");
  act(() => setLocale("zh-CN"));
  expect(disclosure).toHaveAttribute("open");
  expect(within(disclosure).getByRole("button", { name: "SOURCE_TARGET_11" })).toBeInTheDocument();
});

it("fails closed for a mismatched returned disease identity", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValue({
    ...dossier,
    entity: { ...dossier.entity, id: "foreign-disease", name: "FOREIGN_DISEASE" },
  });
  renderWithQueryClient(<DiseaseView {...props} />);
  await screen.findByText("Disease dossier does not match the requested entity");
  expect(screen.queryByRole("heading", { name: "FOREIGN_DISEASE" })).not.toBeInTheDocument();
});

it("keeps a source condition as a registry label in English, not a verified disease", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValue({
    ...dossier,
    entity: {
      ...dossier.entity,
      attributes: {
        identity_scope: "provider_label",
        label_provider: "ClinicalTrials.gov",
        identity_note: "原始标签说明",
      },
    },
  });
  renderWithQueryClient(<DiseaseView {...props} />);
  await screen.findByRole("tablist", { name: "Registry condition dossier sections" });
  expect(screen.getByText("原始标签说明")).toBeInTheDocument();
  expect(screen.queryByText("Highest development phase")).not.toBeInTheDocument();
});
