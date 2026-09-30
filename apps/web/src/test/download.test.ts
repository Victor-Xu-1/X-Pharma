import { expect, it, vi } from "vitest";

import { downloadBlob, exportPayloadToBlob } from "../lib/download";

it("normalizes JSON and CSV payloads without corrupting their content", async () => {
  const json = exportPayloadToBlob({ target: "EGFR", count: 2 }, "json");
  const csv = exportPayloadToBlob("id,name\n1,EGFR\n", "csv");

  expect(json.type).toBe("application/json;charset=utf-8");
  expect(JSON.parse(await json.text())).toEqual({ target: "EGFR", count: 2 });
  expect(csv.type).toBe("text/csv;charset=utf-8");
  expect(await csv.text()).toBe("id,name\n1,EGFR\n");
});

it("rejects text masquerading as an XLSX binary response", () => {
  expect(() => exportPayloadToBlob("not-a-workbook", "xlsx")).toThrow("未返回有效的 XLSX 二进制文件");
});

it("downloads a Blob and always revokes its temporary object URL", () => {
  const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:comparison-export");
  const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  const blob = new Blob(["{}"], { type: "application/json" });

  downloadBlob(blob, "comparison.json");

  expect(createObjectURL).toHaveBeenCalledWith(blob);
  expect(click).toHaveBeenCalledOnce();
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:comparison-export");
  expect(document.querySelector('a[download="comparison.json"]')).toBeNull();
});
