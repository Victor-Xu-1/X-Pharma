import type { FormEvent } from "react";
import type { CommercialOperationRunner } from "./types";
import type { CommercialActionDrafts } from "./useCommercialActionDrafts";

/** Build payloads once at explicit submission; execute through the existing current-read and synchronous workspace boundary. */
export function commercialFormOperations(runOperation: CommercialOperationRunner, drafts: CommercialActionDrafts) {
  async function createBillingDispute(event: FormEvent) {
    event.preventDefault();
    if (
      !drafts.createDisputeAction ||
      !(Number(drafts.disputedUnits) > 0) ||
      drafts.disputeSubject.trim().length < 3 ||
      drafts.reason.trim().length < 3
    )
      return;
    const succeeded = await runOperation(
      "dispute:create:" + drafts.createDisputeAction.delivery.statement_id,
      {
        kind: "create-dispute",
        requestBody: {
          dispute_key: drafts.createDisputeAction.disputeKey,
          statement_id: drafts.createDisputeAction.delivery.statement_id,
          invoice_reference_id: null,
          category: drafts.disputeCategory,
          disputed_units: drafts.disputedUnits,
          subject: drafts.disputeSubject.trim(),
          description: drafts.reason.trim(),
        },
      },
      "计费争议创建失败",
    );
    if (!succeeded) return;
    drafts.setCreateDisputeAction(null);
    drafts.setDisputedUnits("");
    drafts.setDisputeSubject("");
    drafts.setReason("");
  }
  async function transitionBillingDispute(event: FormEvent) {
    event.preventDefault();
    if (!drafts.disputeCaseAction || drafts.reason.trim().length < 3) return;
    const requiresCredit = drafts.disputeCaseAction.action === "resolve_credit";
    if (requiresCredit && (!(Number(drafts.disputedUnits) > 0) || drafts.adjustmentKey.trim().length < 8)) return;
    const succeeded = await runOperation(
      "dispute:" + drafts.disputeCaseAction.dispute.id,
      {
        kind: "transition-dispute",
        disputeId: drafts.disputeCaseAction.dispute.id,
        requestBody: {
          operation_key: drafts.disputeCaseAction.operationKey,
          expected_version: drafts.disputeCaseAction.dispute.version,
          action: drafts.disputeCaseAction.action,
          notes: drafts.reason.trim(),
          assigned_to: drafts.assignee.trim() || null,
          adjustment_key: requiresCredit ? drafts.adjustmentKey.trim() : null,
          credit_units: requiresCredit ? drafts.disputedUnits : null,
        },
      },
      "计费争议处理失败",
    );
    if (!succeeded) return;
    drafts.setDisputeCaseAction(null);
    drafts.setReason("");
    drafts.setAssignee("");
    drafts.setAdjustmentKey("");
    drafts.setDisputedUnits("");
  }
  async function updateCustomerMapping(event: FormEvent) {
    event.preventDefault();
    if (!drafts.mappingAction || drafts.externalReference.trim().length < 1 || drafts.reason.trim().length < 3) return;
    const succeeded = await runOperation(
      "mapping:" + drafts.mappingAction.account.id,
      {
        kind: "update-customer-mapping",
        accountId: drafts.mappingAction.account.id,
        requestBody: { external_customer_reference: drafts.externalReference.trim(), reason: drafts.reason.trim() },
      },
      "计费账户映射更新失败",
    );
    if (!succeeded) return;
    drafts.setMappingAction(null);
    drafts.setExternalReference("");
    drafts.setReason("");
  }
  async function replayDelivery(event: FormEvent) {
    event.preventDefault();
    if (!drafts.replayAction?.delivery.delivery_id || drafts.reason.trim().length < 3) return;
    const succeeded = await runOperation(
      "replay:" + drafts.replayAction.delivery.delivery_id,
      {
        kind: "replay-delivery",
        deliveryId: drafts.replayAction.delivery.delivery_id,
        requestBody: { reason: drafts.reason.trim() },
      },
      "账单投递重放失败",
    );
    if (!succeeded) return;
    drafts.setReplayAction(null);
    drafts.setReason("");
  }
  async function updateClient(event: FormEvent) {
    event.preventDefault();
    if (!drafts.clientAction || !drafts.reason.trim()) return;
    const succeeded = await runOperation(
      "client:" + drafts.clientAction.client.id,
      {
        kind: "update-client",
        clientId: drafts.clientAction.client.id,
        requestBody: { active: drafts.clientAction.active, reason: drafts.reason.trim() },
      },
      "客户端状态更新失败",
    );
    if (!succeeded) return;
    drafts.setClientAction(null);
    drafts.setReason("");
  }
  async function reviewRisk(event: FormEvent) {
    event.preventDefault();
    if (!drafts.riskAction) return;
    const succeeded = await runOperation(
      "risk:" + drafts.riskAction.event.id,
      {
        kind: "review-risk",
        eventId: drafts.riskAction.event.id,
        requestBody: { status: drafts.riskAction.status, notes: drafts.reason.trim() },
      },
      "风险事件处置失败",
    );
    if (!succeeded) return;
    drafts.setRiskAction(null);
    drafts.setReason("");
  }
  return {
    createBillingDispute,
    transitionBillingDispute,
    updateCustomerMapping,
    replayDelivery,
    updateClient,
    reviewRisk,
  };
}
