import { useState } from "react";
import { FormStatus } from "../../components/FormStatus";
import type {
  DataExportJob,
  DataLifecycleEvent,
  DeletedSourceAsset,
  LegalHold,
  SourceAssetImpact,
} from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialLifecycleText as t } from "../../lib/i18n/commercialLifecycle";
import { LegalHoldForm, type LegalHoldInput } from "./lifecycle/LegalHoldForm";
import { LifecycleActionModal } from "./lifecycle/LifecycleActionModal";
import { LifecycleEventRecords } from "./lifecycle/LifecycleEventRecords";
import { LifecycleHoldRecords } from "./lifecycle/LifecycleHoldRecords";
import { LifecyclePurgeRecords } from "./lifecycle/LifecyclePurgeRecords";
import { LifecycleSourceRecords } from "./lifecycle/LifecycleSourceRecords";
import { RetentionPolicyForm, type RetentionPolicyInput } from "./lifecycle/RetentionPolicyForm";
import type { LifecycleAction, LifecycleConfirmation } from "./lifecycle/types";
import type { LifecycleDraftState } from "./lifecycle/useLifecycleDrafts";

type Props = {
  holds: LegalHold[];
  events: DataLifecycleEvent[];
  candidates: DataExportJob[];
  sourceCandidates: SourceAssetImpact[];
  deletedSourceAssets: DeletedSourceAsset[];
  drafts: LifecycleDraftState;
  busy: string;
  error: string;
  refreshing: boolean;
  onActionStart: () => void;
  onSavePolicy: (input: RetentionPolicyInput) => Promise<boolean>;
  onPlaceHold: (input: LegalHoldInput) => Promise<boolean>;
  onReleaseHold: (hold: LegalHold, reason: string) => Promise<boolean>;
  onPurge: (job: DataExportJob, reason: string, key: string) => Promise<boolean>;
  onPurgeSource: (asset: SourceAssetImpact, reason: string, key: string) => Promise<boolean>;
  onReauthorizeSource: (asset: DeletedSourceAsset, reason: string, key: string) => Promise<boolean>;
};
export function DataLifecyclePanel(props: Props) {
  useLocale();
  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const disabled = Boolean(props.busy) || props.refreshing;
  function beginAction(action: LifecycleAction) {
    if (!disabled) {
      props.onActionStart();
      setPendingAction(action);
    }
  }
  const close = () => {
    if (!props.busy) setPendingAction(null);
  };
  const latest =
    pendingAction?.kind === "release"
      ? props.holds.find((item) => item.id === pendingAction.hold.id)
      : pendingAction?.kind === "purge"
        ? props.candidates.find((item) => item.id === pendingAction.job.id)
        : pendingAction?.kind === "source-purge"
          ? props.sourceCandidates.find((item) => item.id === pendingAction.asset.id)
          : pendingAction?.kind === "source-reauthorize"
            ? props.deletedSourceAssets.find((item) => item.id === pendingAction.asset.id)
            : null;
  const captured =
    pendingAction?.kind === "release"
      ? pendingAction.hold
      : pendingAction?.kind === "purge"
        ? pendingAction.job
        : pendingAction?.asset;
  const current = Boolean(latest && captured && JSON.stringify(latest) === JSON.stringify(captured));
  async function confirm(intent: LifecycleConfirmation) {
    if (!pendingAction || disabled || !current || pendingAction.kind !== intent.kind) return false;
    if (pendingAction.kind === "release" && intent.kind === "release")
      return props.onReleaseHold(pendingAction.hold, intent.reason);
    if (intent.kind === "release") return false;
    if (pendingAction.kind === "purge") return props.onPurge(pendingAction.job, intent.reason, intent.key);
    if (pendingAction.kind === "source-purge")
      return props.onPurgeSource(pendingAction.asset, intent.reason, intent.key);
    if (pendingAction.kind === "source-reauthorize")
      return props.onReauthorizeSource(pendingAction.asset, intent.reason, intent.key);
    return false;
  }
  return (
    <section className="lifecycle-workbench" aria-label={t("数据生命周期治理")}>
      {!pendingAction ? <FormStatus pending={Boolean(props.busy)} error={props.error} /> : null}
      <div className="lifecycle-config-grid">
        <RetentionPolicyForm
          policy={props.drafts.exportPolicy}
          draft={props.drafts.exportDraft}
          busy={disabled}
          onSave={props.onSavePolicy}
        />
        <RetentionPolicyForm
          source
          policy={props.drafts.sourcePolicy}
          draft={props.drafts.sourceDraft}
          busy={disabled}
          onSave={props.onSavePolicy}
        />
        <LegalHoldForm drafts={props.drafts} busy={disabled} onPlace={props.onPlaceHold} />
      </div>
      <LifecycleHoldRecords holds={props.holds} busy={disabled ? "lifecycle" : ""} beginAction={beginAction} />
      <LifecycleSourceRecords
        sourceCandidates={props.sourceCandidates}
        deletedSourceAssets={props.deletedSourceAssets}
        busy={disabled ? "lifecycle" : ""}
        beginAction={beginAction}
      />
      <LifecyclePurgeRecords
        candidates={props.candidates}
        busy={disabled ? "lifecycle" : ""}
        beginAction={beginAction}
      />
      <LifecycleEventRecords events={props.events} />
      {pendingAction ? (
        <LifecycleActionModal
          action={pendingAction}
          busy={Boolean(props.busy)}
          error={props.error}
          current={current && !props.refreshing}
          onClose={close}
          onConfirm={confirm}
        />
      ) : null}
    </section>
  );
}
