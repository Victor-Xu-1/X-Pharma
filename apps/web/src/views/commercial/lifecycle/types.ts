import type {
  DataExportJob,
  DeletedSourceAsset,
  LegalHold,
  SourceAssetImpact,
} from "../../../lib/contracts/commercial";
export type LifecycleAction =
  | { kind: "release"; hold: LegalHold }
  | { kind: "purge"; job: DataExportJob }
  | { kind: "source-purge"; asset: SourceAssetImpact }
  | { kind: "source-reauthorize"; asset: DeletedSourceAsset };
