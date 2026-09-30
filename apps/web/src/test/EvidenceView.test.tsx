import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { listEvidenceDatasets, searchEvidence } from "../lib/contracts/evidence";
import { EvidenceView } from "../views/EvidenceView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/evidence", () => ({
  evidenceKeys: {
    datasets: ["evidence", "datasets"],
    search: (query: string, datasetKeys: string[]) => ["evidence", "search", { query, datasetKeys }],
  },
  listEvidenceDatasets: vi.fn(),
  searchEvidence: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(listEvidenceDatasets).mockResolvedValue([
    { attribution: "Open literature", dataset_key: "literature", display_name: "文献" },
  ]);
  vi.mocked(searchEvidence).mockResolvedValue({
    query: "EGFR L858R",
    engine: "opensearch-hybrid",
    license_scopes: [],
    warnings: [],
    chunks: [
      {
        content: "EGFR L858R showed a measured response.",
        dataset_id: "literature",
        document_id: "document-1",
        document_name: "EGFR evidence paper",
        metadata: {
          source: "https://example.test/egfr",
          source_version_id: "private-version-id",
          content_sha256: "a".repeat(64),
        },
        positions: [{ end_char: 280, locator_kind: "page", locator_value: "7", start_char: 120 }],
        similarity: 0.91,
      },
    ],
  });
});

it("submits bounded evidence domains and renders source-bearing results", async () => {
  renderWithQueryClient(<EvidenceView />);

  fireEvent.change(screen.getByPlaceholderText("输入靶点、活性值、专利号、试验号或项目事实"), {
    target: { value: " EGFR L858R " },
  });
  fireEvent.click(await screen.findByRole("button", { name: "文献" }));
  fireEvent.click(screen.getByRole("button", { name: "查证原文" }));

  expect(await screen.findByRole("heading", { name: "EGFR evidence paper" })).toBeInTheDocument();
  expect(vi.mocked(searchEvidence).mock.calls[0]?.[0]).toEqual({
    query: "EGFR L858R",
    datasetKeys: ["literature"],
    signal: expect.any(AbortSignal),
  });
  const record = screen.getByRole("article");
  expect(record.querySelector("blockquote")).toHaveStyle({
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });
  expect(within(record).getByText("文献")).toBeInTheDocument();
  expect(within(record).getByText("Open literature")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "访问原始来源" })).toHaveAttribute("href", "https://example.test/egfr");
  expect(screen.getByText("页 7 · 字符 120-280")).toBeInTheDocument();
  expect(screen.queryByText("检索分 0.91")).not.toBeInTheDocument();
  expect(screen.queryByText("opensearch-hybrid")).not.toBeInTheDocument();
  expect(screen.queryByText("document-1")).not.toBeInTheDocument();
  expect(screen.queryByText("literature", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByText("private-version-id")).not.toBeInTheDocument();
  expect(screen.queryByText("a".repeat(64))).not.toBeInTheDocument();
});

it("collapses long raw citations and keeps the complete citation expandable", async () => {
  const longContent = "EGFR evidence ".repeat(100);
  vi.mocked(searchEvidence).mockResolvedValue({
    query: "EGFR",
    engine: "opensearch-hybrid",
    license_scopes: [],
    warnings: [],
    chunks: [
      {
        content: longContent,
        dataset_id: "literature",
        document_id: "long-document",
        document_name: "Long EGFR evidence",
        metadata: {},
        positions: [],
        similarity: 0.9,
      },
    ],
  });

  renderWithQueryClient(<EvidenceView initialQuery="EGFR" />);

  const record = await screen.findByRole("article");
  expect(record.querySelector("blockquote")).toHaveTextContent(longContent.slice(0, 720));
  fireEvent.click(within(record).getByRole("button", { name: "展开完整引用" }));
  expect(within(record).getByRole("button", { name: "收起完整引用" })).toHaveAttribute("aria-expanded", "true");
  expect(record.querySelector("blockquote")).toHaveTextContent(longContent);
});

it("emits stable query and citation locations and restores a selected real result", async () => {
  const onLocationChange = vi.fn();
  const { rerender } = renderWithQueryClient(<EvidenceView onLocationChange={onLocationChange} />);

  fireEvent.change(screen.getByPlaceholderText("输入靶点、活性值、专利号、试验号或项目事实"), {
    target: { value: " EGFR L858R " },
  });
  fireEvent.click(await screen.findByRole("button", { name: "文献" }));
  fireEvent.click(screen.getByRole("button", { name: "查证原文" }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR L858R",
    datasetKeys: ["literature"],
    documentId: null,
    chunkIndex: null,
  });

  rerender(
    <EvidenceView initialQuery="EGFR L858R" initialDatasetKeys={["literature"]} onLocationChange={onLocationChange} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "定位引用 01" }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR L858R",
    datasetKeys: ["literature"],
    documentId: "document-1",
    chunkIndex: 0,
  });

  rerender(
    <EvidenceView
      initialQuery="EGFR L858R"
      initialDatasetKeys={["literature"]}
      initialDocumentId="document-1"
      initialChunkIndex={0}
      onLocationChange={onLocationChange}
    />,
  );
  expect(await screen.findByLabelText("当前引用定位")).toHaveTextContent("EGFR evidence paper");
  expect(screen.getByLabelText("当前引用定位")).toHaveTextContent("引用 01 · 页 7");
  expect(screen.getByRole("article", { current: true })).toHaveTextContent("EGFR L858R showed a measured response");
});

it("fails closed when a citation locator no longer matches the returned document", async () => {
  const onLocationChange = vi.fn();
  renderWithQueryClient(
    <EvidenceView
      initialQuery="EGFR L858R"
      initialDocumentId="stale-document"
      initialChunkIndex={0}
      onLocationChange={onLocationChange}
    />,
  );

  expect(await screen.findByText("该引用已不在当前检索结果中")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除失效定位" }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR L858R",
    datasetKeys: [],
    documentId: null,
    chunkIndex: null,
  });
});

it("renders an empty evidence-domain state and keeps search disabled", async () => {
  vi.mocked(listEvidenceDatasets).mockResolvedValue([]);

  renderWithQueryClient(<EvidenceView />);

  expect(await screen.findByText("暂无可用证据域")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "证据域加载失败，重试" })).not.toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("输入靶点、活性值、专利号、试验号或项目事实"), {
    target: { value: "EGFR L858R" },
  });
  expect(screen.getByRole("button", { name: "查证原文" })).toBeDisabled();
  expect(searchEvidence).not.toHaveBeenCalled();
});

it("keeps search disabled while evidence domains cannot be loaded", async () => {
  vi.mocked(listEvidenceDatasets).mockRejectedValue(new Error("service unavailable"));

  renderWithQueryClient(<EvidenceView />);

  expect(await screen.findByRole("button", { name: "证据域加载失败，重试" })).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("输入靶点、活性值、专利号、试验号或项目事实"), {
    target: { value: "EGFR L858R" },
  });
  expect(screen.getByRole("button", { name: "查证原文" })).toBeDisabled();
  expect(searchEvidence).not.toHaveBeenCalled();
});
