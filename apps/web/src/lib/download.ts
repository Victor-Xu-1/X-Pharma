export type ExportFormat = "csv" | "json" | "xlsx";

const exportMimeTypes: Record<ExportFormat, string> = {
  csv: "text/csv;charset=utf-8",
  json: "application/json;charset=utf-8",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

export function exportPayloadToBlob(payload: unknown, format: ExportFormat): Blob {
  if (
    payload instanceof Blob ||
    (payload !== null &&
      typeof payload === "object" &&
      typeof (payload as Blob).arrayBuffer === "function" &&
      typeof (payload as Blob).slice === "function")
  ) {
    return payload as Blob;
  }
  if (format === "xlsx") throw new Error("导出服务未返回有效的 XLSX 二进制文件");
  if (format === "csv" && typeof payload !== "string") throw new Error("导出服务未返回有效的 CSV 文本");
  const content = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  return new Blob([content], { type: exportMimeTypes[format] });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}
