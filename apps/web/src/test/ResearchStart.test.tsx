import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResearchStart } from "../components/ResearchStart";

it("runs an explicit example through its existing search callback without representing it as a fact", () => {
  const onSearch = vi.fn();
  render(<ResearchStart onSearch={onSearch} />);
  const examples = screen.getByRole("group", { name: "示例检索" });
  fireEvent.click(within(examples).getByRole("button", { name: "检索示例 HER2" }));
  expect(onSearch).toHaveBeenCalledExactlyOnceWith("HER2");
  expect(screen.getByText(/来源覆盖不等于完整研究结论/)).toBeInTheDocument();
});
