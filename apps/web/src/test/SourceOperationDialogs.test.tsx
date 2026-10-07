import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { IngestionRun } from "../lib/contracts/dataFactory";
import { CancelRunDialog, ReplayRunDialog } from "../views/dataFactory/IngestionRunDialogs";
import { ReplayVersionDialog } from "../views/dataFactory/ReplayVersionDialog";

const run: IngestionRun = {
  id: "reviewed-run",
  data_source_id: "reviewed-source",
  workflow_id: "reviewed-workflow",
  temporal_workflow_id: "reviewed-workflow",
  temporal_run_id: "reviewed-execution",
  state: "running",
  effective_state: "running",
  cancel_requested_at: null,
  cancelable: true,
  progress_percent: 25,
  total_versions: 4,
  completed_versions: 1,
  stages: [],
  counters: {},
  result: {},
  created_at: "2026-10-07T08:00:00Z",
  started_at: "2026-10-07T08:00:00Z",
  heartbeat_at: "2026-10-07T08:01:00Z",
  completed_at: null,
  error_summary: null,
};

type DialogState = {
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (...args: unknown[]) => Promise<void>;
};

function submitDialog() {
  const form = screen.getByRole("dialog").querySelector("form");
  if (!form) throw new Error("Expected an operation form in the dialog");
  fireEvent.submit(form);
}

const cases: { name: string; reasonLabel: string; pendingLabel: string; dialog: (state: DialogState) => ReactNode }[] =
  [
    {
      name: "ingestion replay",
      reasonLabel: "重放原因",
      pendingLabel: "正在提交重放请求",
      dialog: (state) => <ReplayRunDialog run={run} {...state} />,
    },
    {
      name: "ingestion cancellation",
      reasonLabel: "取消原因",
      pendingLabel: "正在提交取消请求",
      dialog: (state) => <CancelRunDialog run={run} {...state} />,
    },
    {
      name: "source version replay",
      reasonLabel: "重放原因",
      pendingLabel: "正在提交版本重放请求",
      dialog: (state) => (
        <ReplayVersionDialog
          versionNumber={3}
          errorCode="parser_unavailable"
          stages={["malware_scan", "parse"]}
          {...state}
        />
      ),
    },
  ];

describe.each(cases)("$name", ({ dialog, reasonLabel, pendingLabel }) => {
  it("locks the submitted input and keeps pending recovery explicit without repeating the request", async () => {
    const state = { busy: false, error: "", onClose: vi.fn(), onConfirm: vi.fn(async () => {}) };
    const view = render(dialog(state));
    const reason = screen.getByRole("textbox", { name: reasonLabel });
    fireEvent.change(reason, { target: { value: "Reviewed reason for this operation" } });
    submitDialog();
    await waitFor(() => expect(state.onConfirm).toHaveBeenCalledOnce());

    view.rerender(dialog({ ...state, busy: true }));
    expect(reason).toBeDisabled();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent(pendingLabel);
    for (const select of screen.queryAllByRole("combobox")) expect(select).toBeDisabled();
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    submitDialog();
    expect(state.onClose).not.toHaveBeenCalled();
    expect(state.onConfirm).toHaveBeenCalledOnce();
  });

  it("retains the original operation key, reason and stage for an explicit retry after rejection", async () => {
    const state = { busy: false, error: "", onClose: vi.fn(), onConfirm: vi.fn(async (..._args: unknown[]) => {}) };
    const view = render(dialog(state));
    const reason = screen.getByRole("textbox", { name: reasonLabel });
    fireEvent.change(reason, { target: { value: "  Reviewed retry reason  " } });
    const stage = screen.queryByRole("combobox");
    if (stage) fireEvent.change(stage, { target: { value: "parse" } });
    submitDialog();
    await waitFor(() => expect(state.onConfirm).toHaveBeenCalledOnce());
    const submitted = state.onConfirm.mock.calls[0];

    view.rerender(dialog({ ...state, busy: true }));
    view.rerender(dialog({ ...state, error: "请求未接受 <script>" }));
    expect(reason).toBeEnabled();
    expect(reason).toHaveValue("  Reviewed retry reason  ");
    if (stage) expect(stage).toHaveValue("parse");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent("请求未接受 <script>");
    expect(document.querySelector("script")).toBeNull();
    submitDialog();
    await waitFor(() => expect(state.onConfirm).toHaveBeenCalledTimes(2));
    expect(state.onConfirm.mock.calls[1]).toEqual(submitted);
    expect(submitted?.at(-1)).toBe("Reviewed retry reason");
  });
});
