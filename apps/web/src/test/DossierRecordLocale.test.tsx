import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DossierActivityTable } from "../components/DossierActivityTable";
import { DossierCoverageDisclosure } from "../components/DossierCoverageDisclosure";
import { PatentTimeline } from "../components/PatentTimeline";
import { setLocale } from "../lib/i18n";
import { News, Patents, Regulatory, Relationships, Structures } from "../views/EntityDossierView";
import { drugDossierFixture as dossier } from "./fixtures/drugDossier";

it("localizes shared missing-record states in standalone panels", () => {
  setLocale("en");
  const onOpen = vi.fn();
  render(
    <>
      <Relationships data={{ ...dossier, relationships: [] }} onOpenEntity={vi.fn()} />
      <Patents data={{ ...dossier, patents: [] }} onOpen={onOpen} onOpenPatent={vi.fn()} />
      <Regulatory data={{ ...dossier, regulatory_events: [] }} onOpen={onOpen} onOpenRegulatoryEvent={vi.fn()} />
      <News data={{ ...dossier, news_events: [] }} onOpen={onOpen} onOpenNewsEvent={vi.fn()} />
      <Structures data={{ ...dossier, structures: [] }} onOpen={onOpen} />
      <DossierActivityTable data={{ ...dossier, activities: [] }} onOpen={onOpen} />
    </>,
  );
  for (const caption of [
    "No linked entity relationships",
    "No linked patents",
    "No linked regulatory events",
    "No linked news or conference updates",
    "No linked chemical structures",
    "No linked bioactivity records",
  ])
    expect(screen.getByText(caption)).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("暂无关联化学结构")).toBeInTheDocument();
});
it("preserves scientific literals and zeros while localizing a shared regulatory record", () => {
  setLocale("en");
  render(<Regulatory data={dossier} onOpen={vi.fn()} onOpenRegulatoryEvent={vi.fn()} />);
  expect(
    screen.getByRole("button", { name: `Open regulatory event: ${dossier.regulatory_events[0].title}` }),
  ).toBeInTheDocument();
  expect(screen.getByText("NDA 219999")).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("NDA 219999")).toBeInTheDocument();
});
it("keeps coverage disclosure closed across switching and translates its count without query ownership", () => {
  setLocale("en");
  render(
    <DossierCoverageDisclosure available={0} total={11}>
      <p>SOURCE CONTENT</p>
    </DossierCoverageDisclosure>,
  );
  expect(screen.getByText("Recorded data and information gaps")).toBeInTheDocument();
  expect(document.querySelector("details")).not.toHaveAttribute("open");
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("0 / 11 个信息领域有记录")).toBeInTheDocument();
  expect(screen.getByText("SOURCE CONTENT")).toBeInTheDocument();
  expect(document.querySelector("details")).not.toHaveAttribute("open");
});

it("preserves unknown patent event codes and duplicated source events literally", () => {
  setLocale("en");
  const error = vi.spyOn(console, "error");
  const event = {
    event_type: "RAW_EVENT_CODE",
    occurred_at: "2026-01-01T00:00:00Z",
    description: "原始 event",
    status: "RAW_STATUS",
  };
  render(
    <PatentTimeline
      patent={{
        id: "patent-1",
        entity_id: "patent-entity-1",
        family_identifier: "SOURCE_FAMILY",
        title: "原始标题",
        priority_date: null,
        expiration_date: null,
        applicants: [],
        inventors: [],
        publications: [],
        legal_status: null,
        legal_status_at: null,
        legal_events: [event, event],
        independent_claims: [],
        linked_entity_ids: [],
        source_document_id: null,
      }}
    />,
  );
  expect(screen.getAllByText("RAW_EVENT_CODE")).toHaveLength(2);
  expect(error.mock.calls.flat().join(" ")).not.toContain("same key");
});
