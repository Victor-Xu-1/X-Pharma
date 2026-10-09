import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadCompanyDossier } from "../lib/contracts/company";
import { setLocale } from "../lib/i18n";
import { CompanyView } from "../views/CompanyView";
import { company, dossier, program } from "./fixtures/companyDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/company", () => ({
  companyKeys: { dossier: (id: string) => ["company-dossier", id] },
  loadCompanyDossier: vi.fn(),
}));
const props = {
  company,
  activeSection: "overview" as const,
  onSectionChange: vi.fn(),
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
  vi.mocked(loadCompanyDossier).mockResolvedValue(dossier);
});

it("localizes company captions while retaining original identity, description and cached reads", async () => {
  renderWithQueryClient(<CompanyView {...props} />);
  await screen.findByRole("tablist", { name: "Organization dossier sections" });
  expect(screen.getByRole("heading", { name: company.name })).toBeInTheDocument();
  expect(screen.getByText(company.description as string)).toBeInTheDocument();
  const reads = vi.mocked(loadCompanyDossier).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("tablist", { name: "公司专业档案视图" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: company.name })).toBeInTheDocument();
  expect(loadCompanyDossier).toHaveBeenCalledTimes(reads);
});
it("fails closed when a returned organization does not match the requested identity", async () => {
  vi.mocked(loadCompanyDossier).mockResolvedValue({
    ...dossier,
    entity: { ...dossier.entity, id: "foreign-company", name: "FOREIGN_COMPANY" },
  });
  renderWithQueryClient(<CompanyView {...props} />);
  await screen.findByText("Organization dossier does not match the requested entity");
  expect(screen.queryByRole("heading", { name: "FOREIGN_COMPANY" })).not.toBeInTheDocument();
});
it("exposes loaded assets beyond the eight-item overview and keeps that disclosure open across languages", async () => {
  vi.mocked(loadCompanyDossier).mockResolvedValue({
    ...dossier,
    programs: Array.from({ length: 10 }, (_, index) => ({
      ...program,
      id: `p-${index}`,
      drug_entity_id: `d-${index}`,
      drug_name: `SOURCE_ASSET_${index}`,
    })),
  });
  const onOpenDrug = vi.fn();
  renderWithQueryClient(<CompanyView {...props} onOpenDrug={onOpenDrug} />);
  const summary = await screen.findByText("More loaded assets (2)");
  fireEvent.click(summary);
  const disclosure = summary.closest("details");
  if (!disclosure) throw Error("Native asset disclosure missing");
  fireEvent.click(within(disclosure).getByRole("button", { name: "SOURCE_ASSET_9" }));
  expect(onOpenDrug).toHaveBeenCalledWith("d-9");
  act(() => setLocale("zh-CN"));
  expect(disclosure).toHaveAttribute("open");
  expect(within(disclosure).getByRole("button", { name: "SOURCE_ASSET_9" })).toBeInTheDocument();
});
it("retains every observed program phase instead of assigning the last program phase to an asset", async () => {
  vi.mocked(loadCompanyDossier).mockResolvedValue({
    ...dossier,
    programs: [
      { ...program, phase: "phase_3" },
      { ...program, id: "other-program", phase: "phase_1" },
    ],
  });
  renderWithQueryClient(<CompanyView {...props} />);
  const asset = await screen.findByRole("list", { name: "Loaded development assets" });
  expect(asset).toHaveTextContent("Phase III");
  expect(asset).toHaveTextContent("Phase I");
  expect(
    screen.getByText("Phases shown belong to returned programs, not a single global drug stage."),
  ).toBeInTheDocument();
});
it("localizes the registry sponsor summary without promoting it to a verified corporate portfolio", async () => {
  const note = "原始 ClinicalTrials.gov label note";
  vi.mocked(loadCompanyDossier).mockResolvedValue({
    ...dossier,
    entity: {
      ...dossier.entity,
      attributes: { identity_scope: "provider_label", label_provider: "ClinicalTrials.gov", identity_note: note },
    },
  });
  renderWithQueryClient(<CompanyView {...props} />);
  await screen.findByRole("region", { name: "Registered clinical studies" });
  expect(screen.getByText("Registry sponsor name")).toBeInTheDocument();
  expect(screen.getByText(note)).toBeInTheDocument();
  expect(screen.queryByText("Highest phase")).not.toBeInTheDocument();
});
