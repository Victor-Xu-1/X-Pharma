import type { PublicationBatch } from "../../lib/contracts/governance";
import type { governancePublicationMessages } from "../../lib/i18n/governancePublication";

type Message = keyof typeof governancePublicationMessages;

export class PublicationResponseError extends Error {
  constructor(readonly key: Message) {
    super(key);
    this.name = "PublicationResponseError";
  }
}
export function completePublicationMembership(batch: PublicationBatch): boolean {
  const items = batch.items;
  return Boolean(
    Array.isArray(items) &&
      batch.expected_count > 0 &&
      items.length === batch.expected_count &&
      items.every((item) => item !== null && typeof item === "object" && typeof item.staged_fact_id === "string") &&
      new Set(items.map((item) => item.staged_fact_id)).size === batch.expected_count,
  );
}
export function assertPublicationPreview(
  batch: PublicationBatch,
  operation: PublicationBatch["operation"],
  ids: string[],
) {
  const requested = [...ids].sort();
  const returned = batch.items?.map((item) => item.staged_fact_id).sort();
  if (
    batch.operation !== operation ||
    !completePublicationMembership(batch) ||
    JSON.stringify(returned) !== JSON.stringify(requested) ||
    !/^[a-f0-9]{64}$/i.test(batch.preview_sha256)
  )
    throw new PublicationResponseError("返回预览与本次操作不匹配");
}
export function assertPublicationCommit(result: PublicationBatch, preview: PublicationBatch) {
  if (
    result.id !== preview.id ||
    result.operation !== preview.operation ||
    result.preview_sha256 !== preview.preview_sha256 ||
    result.status !== "committed"
  )
    throw new PublicationResponseError("批次提交结果与固定预览不匹配");
}
/** The same captured intent retains its key after an uncertain network outcome. */
export function publicationIntentFingerprint(operation: PublicationBatch["operation"], ids: string[], reason: string) {
  return JSON.stringify([operation, [...ids].sort(), reason.trim()]);
}
