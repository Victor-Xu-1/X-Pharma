import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { DossierCoverageDisclosure } from "../components/DossierCoverageDisclosure";

it("keeps missing-data detail mounted and discoverable without repeating every zero row on first view", () => {
  const { rerender } = render(
    <DossierCoverageDisclosure available={0} total={11}>
      <table aria-label="详细收录情况">
        <tbody>
          <tr>
            <td>临床试验 0</td>
          </tr>
        </tbody>
      </table>
    </DossierCoverageDisclosure>,
  );
  expect(document.querySelector("details")).not.toHaveAttribute("open");
  expect(screen.getByText("0 / 11 个信息领域有记录")).toBeInTheDocument();
  fireEvent.click(screen.getByText("数据收录与缺失信息"));
  expect(document.querySelector("table")).toHaveTextContent("临床试验 0");
  rerender(
    <DossierCoverageDisclosure available={1} total={11}>
      <table aria-label="详细收录情况">
        <tbody>
          <tr>
            <td>临床试验 1</td>
          </tr>
        </tbody>
      </table>
    </DossierCoverageDisclosure>,
  );
  expect(document.querySelector("details")).toHaveAttribute("open");
});
