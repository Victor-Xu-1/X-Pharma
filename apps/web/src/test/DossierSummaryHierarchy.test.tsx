import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadCompanyDossier } from "../lib/contracts/company";
import { loadDiseaseDossier } from "../lib/contracts/disease";
import { setLocale } from "../lib/i18n";
import { CompanyView } from "../views/CompanyView";
import { DiseaseView } from "../views/DiseaseView";
import { company, dossier as companyDossier } from "./fixtures/companyDossier";
import { disease, dossier as diseaseDossier } from "./fixtures/diseaseDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/company", () => ({
  companyKeys: { dossier: (id: string) => ["company-dossier", id] },
  loadCompanyDossier: vi.fn(),
}));
vi.mock("../lib/contracts/disease", () => ({
  diseaseKeys: { dossier: (id: string) => ["disease-dossier", id] },
  loadDiseaseDossier: vi.fn(),
}));

const callbacks = {
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
  vi.mocked(loadCompanyDossier).mockResolvedValue(companyDossier);
  vi.mocked(loadDiseaseDossier).mockResolvedValue(diseaseDossier);
});

it.each(["organization", "disease"] as const)(
  "keeps three primary %s facts and preserves every secondary fact across locale changes",
  async (kind) => {
    renderWithQueryClient(
      kind === "organization" ? (
        <CompanyView company={company} activeSection="overview" {...callbacks} />
      ) : (
        <DiseaseView disease={disease} activeSection="overview" onOpenEpidemiology={vi.fn()} {...callbacks} />
      ),
    );
    const entity = kind === "organization" ? company : disease;
    await screen.findByRole("heading", { name: entity.name });
    const primary = document.querySelector(".company-profile-metrics");
    expect(primary?.childElementCount).toBe(3);
    expect(primary).toHaveTextContent("Phase II");
    const disclosure = document.querySelector(".dossier-summary-details");
    expect(disclosure).not.toHaveAttribute("open");
    expect(disclosure).not.toBeNull();
    fireEvent.click(within(disclosure as HTMLElement).getByText("More dossier facts"));
    expect(disclosure).toHaveAttribute("open");
    const secondary = disclosure?.querySelector("dl");
    expect(secondary?.childElementCount).toBe(3);
    expect(secondary).toHaveTextContent(
      kind === "organization"
        ? "Linked deals1Dated events2"
        : "Disease burden observations1Clinical trials / patents0 / 0",
    );
    expect(secondary).toHaveTextContent("Latest activity");
    act(() => setLocale("zh-CN"));
    expect(disclosure).toHaveAttribute("open");
    expect(within(disclosure as HTMLElement).getByText("更多档案指标")).toBeVisible();
    expect(secondary).toHaveTextContent("最近活动");
    expect(primary).toHaveTextContent("II 期临床");
    expect(document.querySelector(".company-profile-identity h2")).toHaveTextContent(entity.name);
    expect(loadCompanyDossier).toHaveBeenCalledTimes(kind === "organization" ? 1 : 0);
    expect(loadDiseaseDossier).toHaveBeenCalledTimes(kind === "disease" ? 1 : 0);
    expect(callbacks.onSectionChange).not.toHaveBeenCalled();
  },
);
