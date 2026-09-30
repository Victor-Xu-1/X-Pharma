import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScrollableTableRegion } from "../components/ScrollableTableRegion";

describe("ScrollableTableRegion", () => {
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
