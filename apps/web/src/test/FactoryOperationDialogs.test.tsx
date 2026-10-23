import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { IngestionRun } from "../lib/contracts/dataFactory";
import { setLocale } from "../lib/i18n";
import { CancelRunDialog } from "../views/dataFactory/IngestionRunDialogs";
import { ReplayVersionDialog } from "../views/dataFactory/ReplayVersionDialog";

const run = { id: "controlled-run", workflow_id: "原始 workflow <Source>" } as IngestionRun;

it("keeps a cancellation reason across language changes and synchronously rejects duplicate pending submissions", async () => {
  setLocale("en");
  let release!: () => void;
  const onConfirm = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        release = resolve;
      }),
  );
  const onClose = vi.fn();
  const view = render(<CancelRunDialog run={run} busy={false} error="" onClose={onClose} onConfirm={onConfirm} />);
  fireEvent.change(screen.getByLabelText("Cancellation reason"), { target: { value: "原始取消原因" } });
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("取消原因")).toHaveValue("原始取消原因");
  const form = screen.getByRole("dialog").querySelector("form");
  if (!form) throw Error("Dialog form missing");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  expect(onConfirm).toHaveBeenCalledOnce();
  expect(onConfirm).toHaveBeenCalledWith(expect.stringMatching(/^ingestion-cancel:controlled-run:/), "原始取消原因");
  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  expect(onClose).not.toHaveBeenCalled();
  view.rerender(<CancelRunDialog run={run} busy error="" onClose={onClose} onConfirm={onConfirm} />);
  act(() => setLocale("en"));
  expect(screen.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
  expect(screen.getByLabelText("Cancellation reason")).toHaveValue("原始取消原因");
  expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
  await act(async () => {
    release();
  });
});

it("keeps the chosen source recovery stage, raw code and reason when translating a failed retry", () => {
  setLocale("en");
  render(
    <ReplayVersionDialog
      versionNumber={2}
      errorCode="RAW_PARSE_CODE"
      stages={["malware_scan", "parse"]}
      busy={false}
      error="RAW_REPLAY_FAILURE"
      onClose={vi.fn()}
      onConfirm={vi.fn()}
    />,
  );
  fireEvent.change(screen.getByLabelText("Recovery start stage"), { target: { value: "malware_scan" } });
  fireEvent.change(screen.getByLabelText("Replay reason"), { target: { value: "原始恢复原因" } });
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("恢复起点")).toHaveValue("malware_scan");
  expect(screen.getByLabelText("重放原因")).toHaveValue("原始恢复原因");
  expect(screen.getByRole("alert")).toHaveTextContent("RAW_REPLAY_FAILURE");
  expect(screen.getByText("RAW_PARSE_CODE")).toBeInTheDocument();
});
