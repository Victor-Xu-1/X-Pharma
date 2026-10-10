import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { ClientTable } from "../views/commercial/ClientTable";
import { RecordDetails, RecordFacts, RecordList } from "../views/commercial/RecordDetails";

beforeEach(() => setLocale("en"));
async function expand(summary: HTMLElement) {
  summary.focus();
  fireEvent.click(summary);
  await waitFor(() => expect(summary).toHaveAttribute("aria-expanded", "true"));
  return summary;
}
it("keeps optional record content out of the initial presentation and preserves an open dialog across locale changes", async () => {
  render(
    <RecordDetails name="Original record <source>">
      <RecordFacts fields={[{ label: "说明", value: "Original description <source>" }]} />
    </RecordDetails>,
  );
  expect(screen.queryByText("Original description <source>")).not.toBeInTheDocument();
  const details = await expand(screen.getByText("Record details"));
  expect(await screen.findByText("Original description <source>")).toBeInTheDocument();
  await act(async () => setLocale("zh-CN"));
  expect(details).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("dialog", { name: "Original record <source> 的记录详情" })).toHaveTextContent(
    "Original description <source>",
  );
  expect(screen.getByText("说明")).toBeInTheDocument();
});
it("distinguishes missing record values from returned zero, false and original decimal precision", () => {
  render(
    <RecordFacts
      fields={[
        { label: "已配置映射", value: false },
        { label: "最大结果行数", value: 0 },
        { label: "每日额度上限", value: "0.000000001" },
        { label: "说明", value: null },
      ]}
    />,
  );
  expect(screen.getByText("No", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("0", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("0.000000001", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("Not reported", { exact: true })).toBeInTheDocument();
});
it("returns keyboard focus to the exact opener when the read-only dialog closes", async () => {
  render(
    <RecordDetails name="Original record">
      <RecordFacts fields={[{ label: "说明", value: "Original description" }]} />
    </RecordDetails>,
  );
  const opener = screen.getByRole("button", { name: "View record details for Original record" });
  await expand(opener);
  const dialog = await screen.findByRole("dialog");
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await waitFor(() => expect(opener).toHaveFocus());
});
it("exposes inactive as well as active subject identities rather than only a count", async () => {
  render(
    <ClientTable
      busy=""
      onAction={() => {
        throw new Error("Read-only inspection must not mutate a client");
      }}
      items={[
        {
          id: "controlled-client",
          client_key: "CONTROLLED_KEY",
          display_name: "Original client <source>",
          active: true,
          active_reservations: 0,
          available_units: "0.000000001",
          billing_account_key: null,
          subscription_key: null,
          subscription_status: null,
          denial_count_24h: 0,
          last_policy_event_at: null,
          created_at: "2026-10-10T00:00:00Z",
          subjects: [{ subject_id: "Original inactive <source>", actor_type: "service", active: false }],
        },
      ]}
    />,
  );
  await expand(screen.getByText("Record details"));
  expect(await screen.findByText("Original inactive <source>")).toBeInTheDocument();
  expect(screen.getByText("service", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("No", { exact: true })).toBeInTheDocument();
});
it("distinguishes an explicitly returned empty list from an unreported value", () => {
  render(<RecordList values={[]} />);
  expect(screen.getByText("No items returned", { exact: true })).toBeInTheDocument();
  expect(screen.queryByText("Not reported", { exact: true })).not.toBeInTheDocument();
});
it("preserves repeated source-owned list entries instead of deduplicating record data", () => {
  render(<RecordList values={["original.field", "original.field", "other.field"]} />);
  expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "original.field",
    "original.field",
    "other.field",
  ]);
});
