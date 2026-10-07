import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { FormStatus } from "../components/FormStatus";

it("announces only the active operation and clears its previous error while pending", () => {
  const { rerender } = render(<FormStatus pending={false} error="操作被拒绝" />);
  expect(screen.getByRole("alert")).toHaveTextContent("操作被拒绝");
  rerender(<FormStatus pending error="操作被拒绝" />);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("正在提交操作");
  rerender(<FormStatus pending={false} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("renders error content as literal text without executing markup", () => {
  render(<FormStatus pending={false} error={'<img src="remote.invalid" onerror="alert(1)" />'} />);
  expect(screen.getByRole("alert")).toHaveTextContent("<img");
  expect(document.querySelector(".form-status img")).toBeNull();
});
