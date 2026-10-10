import { act, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import {
  dataFactoryKeys,
  decideQuarantineCase,
  loadQuarantineCase,
  loadSourceAsset,
} from "../lib/contracts/dataFactory";
import type { SourceAssetDetailRead, SourceVersionQuarantineCaseRead } from "../lib/generated";
import { setLocale } from "../lib/i18n";
import { quarantineActionLabel, quarantineDecisionLabel, quarantineStatusLabel } from "../lib/quarantinePresentation";
import { QuarantineDecisionDialog } from "../views/dataFactory/QuarantineDecisionDialog";
import { SourceAssetDrawer } from "../views/dataFactory/SourceAssetDrawer";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/dataFactory", async (original) => ({
  ...(await original<typeof import("../lib/contracts/dataFactory")>()),
  loadQuarantineCase: vi.fn(),
  decideQuarantineCase: vi.fn(),
  loadSourceAsset: vi.fn(),
}));

const asset: SourceAssetDetailRead = {
  id: "requested-asset",
  data_source_id: "controlled-source",
  logical_path: "原始文件.pdf",
  source_uri: "file:///sources/original.pdf",
  file_name: "原始文件.pdf",
  extension: ".pdf",
  media_type: "application/pdf",
  state: "active",
  processing_mode: "parse",
  current_version_id: null,
  first_seen_at: "2026-01-01T00:00:00Z",
  last_seen_at: "2026-01-01T00:00:00Z",
  missing_since: null,
  versions: [],
};
const quarantineCase: SourceVersionQuarantineCaseRead = {
  source_version_id: "requested-version",
  source_asset_id: asset.id,
  file_name: "原始隔离文件.pdf",
  logical_path: asset.logical_path,
  quarantine_status: "pending_review",
  quarantine_version: 1,
  updated_at: "2026-01-01T00:00:00Z",
  error_code: "malware_detected",
  error_message: "RAW_MALWARE",
  threat_name: "RAW_THREAT",
  decisions: [],
};

it("rejects an asset detail whose identifier differs from the requested record", async () => {
  setLocale("en");
  vi.mocked(loadSourceAsset).mockResolvedValue({ ...asset, id: "other-asset" });
  renderWithQueryClient(<SourceAssetDrawer assetId={asset.id} canManage onClose={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Source asset does not match the requested identifier");
  expect(screen.queryByText(asset.file_name)).not.toBeInTheDocument();
});

it("hides cached source versions after a current permission denial instead of retaining their title", async () => {
  setLocale("en");
  vi.mocked(loadSourceAsset).mockResolvedValue(asset);
  const { queryClient } = renderWithQueryClient(<SourceAssetDrawer assetId={asset.id} canManage onClose={vi.fn()} />);
  await screen.findByRole("heading", { name: asset.file_name });
  vi.mocked(loadSourceAsset).mockRejectedValue(new ApiError("RAW_ASSET_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: dataFactoryKeys.asset(asset.id), exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_ASSET_DENIAL");
  expect(screen.queryByText(asset.file_name)).not.toBeInTheDocument();
});

it("rejects a quarantine case bound to another source version", async () => {
  setLocale("en");
  vi.mocked(loadQuarantineCase).mockResolvedValue({ ...quarantineCase, source_version_id: "other-version" });
  renderWithQueryClient(
    <QuarantineDecisionDialog
      versionId={quarantineCase.source_version_id}
      canManage
      onClose={vi.fn()}
      onDecided={vi.fn()}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Quarantine case does not match the requested source version",
  );
  expect(screen.queryByText(quarantineCase.file_name)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Submit decision" })).not.toBeInTheDocument();
});

it("hides cached quarantine facts and write controls when authorization is revoked", async () => {
  setLocale("en");
  vi.mocked(loadQuarantineCase).mockResolvedValue(quarantineCase);
  const { queryClient } = renderWithQueryClient(
    <QuarantineDecisionDialog
      versionId={quarantineCase.source_version_id}
      canManage
      onClose={vi.fn()}
      onDecided={vi.fn()}
    />,
  );
  await screen.findByText(quarantineCase.file_name);
  vi.mocked(loadQuarantineCase).mockRejectedValue(new ApiError("RAW_QUARANTINE_DENIAL", 403, null));
  await act(() =>
    queryClient.refetchQueries({ queryKey: dataFactoryKeys.quarantine(quarantineCase.source_version_id), exact: true }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_QUARANTINE_DENIAL");
  expect(screen.queryByText(quarantineCase.file_name)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Submit decision" })).not.toBeInTheDocument();
  expect(decideQuarantineCase).not.toHaveBeenCalled();
});

it("retains prototype-like unknown quarantine vocabulary as literal source codes", () => {
  setLocale("en");
  expect(quarantineStatusLabel("constructor")).toBe("constructor");
  expect(quarantineActionLabel("__proto__")).toBe("__proto__");
  expect(quarantineDecisionLabel("toString")).toBe("toString");
});
