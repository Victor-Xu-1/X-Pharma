import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KeyboardScrollRegion } from "../components/KeyboardScrollRegion";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";

describe("ScrollableTableRegion", () => {
  it("shares keyboard access with non-table diagnostic content without inventing a table role", () => {
    render(
      <KeyboardScrollRegion ariaLabel="Query feedback" className="diagnostic-region">
        <p>原始来源原因 / Raw source reason</p>
      </KeyboardScrollRegion>,
    );
    const region = screen.getByRole("region", { name: "Query feedback" });
    region.focus();
    expect(region).toHaveFocus();
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveTextContent("原始来源原因 / Raw source reason");
    expect(region).not.toHaveClass("table-frame");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
  it("exposes a named keyboard-scrollable region", () => {
    render(
      <ScrollableTableRegion ariaLabel="临床结果明细" className="custom-table-frame">
        <table aria-label="临床结果">
          <tbody>
            <tr>
              <td>ORR</td>
            </tr>
          </tbody>
        </table>
      </ScrollableTableRegion>,
    );

    const region = screen.getByRole("region", { name: "临床结果明细" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveClass("table-frame", "custom-table-frame");
    expect(screen.getByRole("table", { name: "临床结果" })).toBeVisible();
  });
});
