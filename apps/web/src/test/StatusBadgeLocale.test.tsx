import { act, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatusBadge } from "../components/common";
import { setLocale } from "../lib/i18n";

it.each(["__proto__", "constructor", "toString", "unrecognized_future_code"])(
  "keeps unknown status %s literal instead of reading inherited captions or rewriting the code",
  (value) => {
    setLocale("en");
    render(<StatusBadge value={value} />);
    expect(screen.getByText(value, { exact: true })).toBeVisible();
    act(() => setLocale("zh-CN"));
    expect(screen.getByText(value, { exact: true })).toBeVisible();
  },
);

it("retains controlled status translation and explicit caller captions", () => {
  setLocale("en");
  render(
    <>
      <StatusBadge value="available" />
      <StatusBadge value="__proto__" label="原始调用方 caption" />
    </>,
  );
  expect(screen.getByText("Available", { exact: true })).toBeVisible();
  expect(screen.getByText("原始调用方 caption", { exact: true })).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("可查看", { exact: true })).toBeVisible();
});
