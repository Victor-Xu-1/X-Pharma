import { act, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ApiError } from "../lib/api";
import { loadRecordProvenance } from "../lib/contracts/provenance";
import { setLocale } from "../lib/i18n";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/provenance", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/provenance")>();
  return {
    ...actual,
    loadRecordProvenance: vi.fn().mockResolvedValue({
      resource_type: "target_evidence",
      resource_id: "record-1",
      license_scopes: [],
      warnings: ["Dataset projects license policy omitted fields: source_document_id"],
      items: [
        {
          id: "provenance-1",
          resource_type: "target_evidence",
          resource_id: "record-1",
          dataset_key: "internal-dataset-key",
          document_name: "EGFR study",
          quote: "EGFR activity was observed.",
          locator: "page=7;paragraph=2",
          source_document_id: "document-internal-1",
          source_version_id: "version-internal-1",
          content_sha256: "hash-internal-1",
          created_at: "2026-08-08T00:00:00Z",
          license: { attribution: "Tenant-provided source material" },
          review_status: "verified",
          warnings: ["internal projection warning: source_document_id"],
        },
      ],
    }),
  };
});

describe("RecordProvenanceDrawer", () => {
  it.each([401, 403])("does not expose cached original evidence after the current read returns %s", async (status) => {
    const selection = { resourceType: "target_evidence" as const, resourceId: "record-1", label: "Evidence" };
    const rendered = renderWithQueryClient(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    await screen.findByText("EGFR activity was observed.");
    vi.mocked(loadRecordProvenance).mockRejectedValueOnce(new ApiError("RAW_SOURCE_DENIAL", status, null));
    await act(async () => {
      await rendered.queryClient.refetchQueries({ queryKey: ["provenance", "target_evidence", "record-1"] });
    });
    await screen.findByText("RAW_SOURCE_DENIAL");
    expect(screen.queryByText("EGFR activity was observed.")).not.toBeInTheDocument();
    expect(screen.queryByText("EGFR study")).not.toBeInTheDocument();
  });

  it("refuses an evidence response for a different requested resource", async () => {
    const selection = { resourceType: "target_evidence" as const, resourceId: "record-1", label: "Evidence" };
    const seed = await vi.mocked(loadRecordProvenance).getMockImplementation()?.(selection);
    if (!seed) throw new Error("Expected original controlled provenance fixture");
    vi.mocked(loadRecordProvenance).mockResolvedValueOnce({ ...seed, resource_id: "foreign" });
    setLocale("en");
    renderWithQueryClient(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    await screen.findByText("Evidence response does not match the requested record");
    expect(screen.queryByText("EGFR activity was observed.")).not.toBeInTheDocument();
  });
  it("shows readable evidence without internal provenance identifiers", async () => {
    renderWithQueryClient(
      <RecordProvenanceDrawer
        selection={{ resourceType: "target_evidence", resourceId: "record-1", label: "EGFR evidence" }}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(vi.mocked(loadRecordProvenance)).toHaveBeenCalledOnce();
      expect(document.body).toHaveTextContent("EGFR study");
    });

    expect(document.body).toHaveTextContent("EGFR study");
    expect(document.body).toHaveTextContent("page=7;paragraph=2");
    expect(document.body).toHaveTextContent("已提供原文片段");
    expect(document.body).not.toHaveTextContent("internal-dataset-key");
    expect(document.body).not.toHaveTextContent("document-internal-1");
    expect(document.body).not.toHaveTextContent("version-internal-1");
    expect(document.body).not.toHaveTextContent("hash-internal-1");
    expect(document.body).not.toHaveTextContent("Dataset projects license policy");
    expect(document.body).not.toHaveTextContent("Tenant-provided source material");
    expect(document.body).not.toHaveTextContent("internal projection warning");
    expect(document.body).not.toHaveTextContent("已查证");
    expect(document.body).toHaveTextContent("部分技术字段因来源许可限制未展示。");
    expect(document.body).toHaveTextContent("部分来源信息暂未展示。");
    expect(document.body).toHaveTextContent("用户提供的来源材料");
  });

  it("localizes evidence headings without changing the original quote, locator or cached read", async () => {
    const selection = { resourceType: "target_evidence" as const, resourceId: "record-1", label: "原始记录 EGFR" };
    const { rerender } = renderWithQueryClient(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    await screen.findByText("EGFR study");
    const reads = vi.mocked(loadRecordProvenance).mock.calls.length;
    act(() => setLocale("en"));
    rerender(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Original evidence" })).toBeVisible();
    expect(screen.getByText("Original text excerpt provided")).toBeVisible();
    expect(screen.getByText("EGFR activity was observed.")).toBeVisible();
    expect(screen.getByText("page=7;paragraph=2")).toBeVisible();
    expect(screen.getByText("原始记录 EGFR")).toBeVisible();
    expect(loadRecordProvenance).toHaveBeenCalledTimes(reads);
  });

  it("retains complete non-boilerplate attribution instead of discarding a required credit", async () => {
    const selection = { resourceType: "target_evidence" as const, resourceId: "record-1", label: "Evidence" };
    const seed = await vi.mocked(loadRecordProvenance).getMockImplementation()?.(selection);
    if (!seed) throw new Error("Expected controlled provenance fixture");
    const credit = "Tenant-provided source material; required credit: 原始作者 Research Institute";
    vi.mocked(loadRecordProvenance).mockResolvedValueOnce({
      ...seed,
      items: [{ ...seed.items[0], license: { ...seed.items[0].license, attribution: credit } }],
    });
    renderWithQueryClient(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    expect(await screen.findByText(credit)).toBeVisible();
  });

  it("does not invent a licensing reason when document names, excerpts and attribution are absent", async () => {
    const selection = { resourceType: "target_evidence" as const, resourceId: "record-1", label: "Evidence" };
    const seed = await vi.mocked(loadRecordProvenance).getMockImplementation()?.(selection);
    if (!seed) throw new Error("Expected controlled provenance fixture");
    vi.mocked(loadRecordProvenance).mockResolvedValueOnce({
      ...seed,
      warnings: [],
      items: [
        {
          ...seed.items[0],
          document_name: "",
          quote: "",
          warnings: [],
          license: { ...seed.items[0].license, attribution: null },
        },
      ],
    });
    act(() => setLocale("en"));
    renderWithQueryClient(<RecordProvenanceDrawer selection={selection} onClose={vi.fn()} />);
    expect(await screen.findByText("Document name not provided")).toBeVisible();
    expect(screen.getByText("Source attribution not provided")).toBeVisible();
    expect(screen.getByText("No original text excerpt is available for display.")).toBeVisible();
    expect(screen.queryByText(/license restriction/i)).not.toBeInTheDocument();
  });
});
