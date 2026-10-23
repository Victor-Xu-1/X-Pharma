import { useState } from "react";
import type { BillingDisputeCategory } from "../../lib/contracts/commercial";
import type {
  ClientAction,
  CreateDisputeAction,
  DisputeCaseAction,
  MappingAction,
  ReplayAction,
  RiskAction,
} from "./types";

/** The only owner of these six mounted action forms. Locale changes do not recreate drafts. */
export function useCommercialActionDrafts() {
  const [clientAction, setClientAction] = useState<ClientAction | null>(null);
  const [riskAction, setRiskAction] = useState<RiskAction | null>(null);
  const [mappingAction, setMappingAction] = useState<MappingAction | null>(null);
  const [replayAction, setReplayAction] = useState<ReplayAction | null>(null);
  const [createDisputeAction, setCreateDisputeAction] = useState<CreateDisputeAction | null>(null);
  const [disputeCaseAction, setDisputeCaseAction] = useState<DisputeCaseAction | null>(null);
  const [externalReference, setExternalReference] = useState("");
  const [reason, setReason] = useState("");
  const [disputeCategory, setDisputeCategory] = useState<BillingDisputeCategory>("usage");
  const [disputedUnits, setDisputedUnits] = useState("");
  const [disputeSubject, setDisputeSubject] = useState("");
  const [assignee, setAssignee] = useState("");
  const [adjustmentKey, setAdjustmentKey] = useState("");
  return {
    clientAction,
    setClientAction,
    riskAction,
    setRiskAction,
    mappingAction,
    setMappingAction,
    replayAction,
    setReplayAction,
    createDisputeAction,
    setCreateDisputeAction,
    disputeCaseAction,
    setDisputeCaseAction,
    externalReference,
    setExternalReference,
    reason,
    setReason,
    disputeCategory,
    setDisputeCategory,
    disputedUnits,
    setDisputedUnits,
    disputeSubject,
    setDisputeSubject,
    assignee,
    setAssignee,
    adjustmentKey,
    setAdjustmentKey,
  };
}
export type CommercialActionDrafts = ReturnType<typeof useCommercialActionDrafts>;
