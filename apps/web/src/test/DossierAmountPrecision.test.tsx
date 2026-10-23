import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { CompanyTimelineResult, DealSearchItemRead } from "../lib/generated";
import { setLocale } from "../lib/i18n";
import { CompanyTimelinePanel } from "../views/dossier/CompanyTimelinePanel";
import { Deals } from "../views/dossier/Deals";
import { drugDossierFixture as dossier } from "./fixtures/drugDossier";

// Synthetic test-only records: never sent to the business service.
const variants = ["deals", "timeline"] as const;
const amounts = [
  { value: 0.000123456, expected: "0.000123456" },
  { value: 25_123_456.75, expected: "25,123,456.75" },
  { value: 0, expected: "0" },
] as const;

it.each(variants.flatMap((variant) => amounts.map((amount) => ({ variant, ...amount }))))(
  "retains $expected and its original currency in $variant through language switching",
  ({ variant, value, expected }) => {
    setLocale("en");
    const baseDeal = dossier.deals[0];
    if (!baseDeal) throw new Error("Explicit synthetic deal fixture is required");
    const deal: DealSearchItemRead = {
      ...baseDeal,
      currency: "RAW_CURRENCY",
      total_potential_amount: value,
    };
    const original = structuredClone(deal);
    const onOpen = vi.fn();
    const onOpenEntity = vi.fn();
    const onOpenDeal = vi.fn();
    if (variant === "deals") {
      render(
        <Deals
          data={{ ...dossier, deals: [deal] }}
          onOpen={onOpen}
          onOpenEntity={onOpenEntity}
          onOpenDeal={onOpenDeal}
        />,
      );
    } else {
      const timeline: CompanyTimelineResult = {
        company: { ...dossier.entity, entity_type: "organization" },
        as_of: dossier.as_of,
        total: 1,
        limit: 1,
        offset: 0,
        items: [
          {
            id: "controlled-deal-event",
            event_type: "deal_announced",
            occurred_at: "2026-06-20T00:00:00Z",
            title: deal.name,
            deal,
          },
        ],
      };
      render(
        <CompanyTimelinePanel
          timeline={timeline}
          loading={false}
          error={null}
          retry={vi.fn()}
          onOpen={onOpen}
          onOpenEntity={onOpenEntity}
        />,
      );
    }
    for (const locale of ["en", "zh-CN", "en"] as const) {
      act(() => setLocale(locale));
      expect(screen.getByText(`RAW_CURRENCY ${expected}`, { exact: false })).toBeInTheDocument();
      expect(screen.getByText(deal.name, { exact: true })).toBeInTheDocument();
      expect(deal).toEqual(original);
      expect(onOpen).not.toHaveBeenCalled();
      expect(onOpenEntity).not.toHaveBeenCalled();
      expect(onOpenDeal).not.toHaveBeenCalled();
    }
  },
);
