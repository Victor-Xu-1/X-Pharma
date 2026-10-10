import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { setLocale } from "../lib/i18n";
import { SourceDraftValidationError } from "../views/dataFactory/sourceDraftValidation";
import { useFactoryOperation } from "../views/dataFactory/useFactoryOperation";

it("starts one synchronous intent and prevents overlapping factory operations", async () => {
  let release!: () => void;
  const request = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        release = resolve;
      }),
  );
  const other = vi.fn();
  const { result } = renderHook(useFactoryOperation);
  let pending!: Promise<boolean>;
  act(() => {
    pending = result.current.execute("one", "操作失败", request);
  });
  expect(result.current.busy).toBe("one");
  expect(await result.current.execute("two", "操作失败", other)).toBe(false);
  expect(other).not.toHaveBeenCalled();
  await act(async () => {
    release();
    await pending;
  });
  expect(result.current.busy).toBe("");
});

it("keeps raw provider errors literal and translates only its typed interface fallback", async () => {
  setLocale("en");
  const { result } = renderHook(useFactoryOperation);
  await act(async () => {
    await result.current.execute("raw", "操作失败", async () => {
      throw new Error("原始服务商错误 <RAW>");
    });
  });
  expect(result.current.error).toBe("原始服务商错误 <RAW>");
  act(() => setLocale("zh-CN"));
  expect(result.current.error).toBe("原始服务商错误 <RAW>");
  await act(async () => {
    await result.current.execute("fallback", "操作失败", async () => {
      throw null;
    });
  });
  expect(result.current.error).toBe("操作失败");
  act(() => setLocale("en"));
  expect(result.current.error).toBe("Operation failed");
});

it("marks a late response as detached so its owner does not close or refresh a different screen", async () => {
  let release!: () => void;
  const response = new Promise<void>((resolve) => {
    release = resolve;
  });
  const accepted = vi.fn();
  const { result, unmount } = renderHook(useFactoryOperation);
  let pending!: Promise<boolean>;
  act(() => {
    pending = result.current.execute("late", "操作失败", async (current) => {
      await response;
      if (current()) accepted();
    });
  });
  unmount();
  await act(async () => {
    release();
    await pending;
  });
  expect(accepted).not.toHaveBeenCalled();
});

it("retains typed validation parameters and translates their framing without another request", async () => {
  setLocale("en");
  const { result } = renderHook(useFactoryOperation);
  const work = vi.fn(async () => {
    throw new SourceDraftValidationError("每页请求数量必须是 1–{maximum} 的整数", { maximum: 200 });
  });
  await act(async () => {
    await result.current.execute("validation", "注册失败", work);
  });
  expect(result.current.error).toBe("Records per request page must be an integer from 1 to 200");
  act(() => setLocale("zh-CN"));
  expect(result.current.error).toBe("每页请求数量必须是 1–200 的整数");
  expect(work).toHaveBeenCalledOnce();
});
