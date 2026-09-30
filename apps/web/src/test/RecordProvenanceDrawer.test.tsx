import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { loadRecordProvenance } from "../lib/contracts/provenance";
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
});
