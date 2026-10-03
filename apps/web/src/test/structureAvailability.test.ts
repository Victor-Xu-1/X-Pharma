import { expect, it, vi } from "vitest";
import { observeStructureAvailability } from "../lib/structureAvailability";

function deferred() {
  let resolve!: (value: string) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<string>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

it("enables drawn structures and disables an empty canvas after real change notifications", async () => {
  let changed!: () => void;
  const read = vi.fn().mockResolvedValueOnce("").mockResolvedValueOnce("c1ccccc1").mockResolvedValueOnce("");
  const update = vi.fn();
  const unsubscribe = vi.fn();
  const stop = observeStructureAvailability({
    subscribe: (notify) => {
      changed = notify;
      return unsubscribe;
    },
    read,
    update,
    fail: vi.fn(),
  });
  await vi.waitFor(() => expect(update).toHaveBeenLastCalledWith(false));
  changed();
  await vi.waitFor(() => expect(update).toHaveBeenLastCalledWith(true));
  changed();
  await vi.waitFor(() => expect(update).toHaveBeenLastCalledWith(false));
  stop();
  expect(unsubscribe).toHaveBeenCalledOnce();
});

it("coalesces drawing changes and ignores a serialization result from an older revision", async () => {
  let changed!: () => void;
  const first = deferred();
  const latest = deferred();
  const read = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(latest.promise);
  const update = vi.fn();
  const stop = observeStructureAvailability({
    subscribe: (notify) => {
      changed = notify;
      return vi.fn();
    },
    read,
    update,
    fail: vi.fn(),
  });
  for (let index = 0; index < 20; index += 1) changed();
  expect(read).toHaveBeenCalledOnce();
  first.resolve("");
  await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  expect(update).not.toHaveBeenCalled();
  latest.resolve("CCO");
  await vi.waitFor(() => expect(update).toHaveBeenCalledWith(true));
  stop();
});

it("reports serialization failures and prevents updates after disposal", async () => {
  let changed!: () => void;
  const pending = deferred();
  const failure = new Error("WASM serialization failed");
  const read = vi.fn().mockRejectedValueOnce(failure).mockReturnValueOnce(pending.promise);
  const update = vi.fn();
  const fail = vi.fn();
  const stop = observeStructureAvailability({
    subscribe: (notify) => {
      changed = notify;
      return vi.fn();
    },
    read,
    update,
    fail,
  });
  await vi.waitFor(() => expect(fail).toHaveBeenCalledWith(failure));
  expect(update).toHaveBeenLastCalledWith(false);
  changed();
  const signal = read.mock.calls[1][0] as AbortSignal;
  stop();
  expect(signal.aborted).toBe(true);
  pending.resolve("CCO");
  await pending.promise;
  expect(update).toHaveBeenCalledOnce();
});
