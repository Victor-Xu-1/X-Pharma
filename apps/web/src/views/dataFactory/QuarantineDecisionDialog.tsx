import { useQuery } from "@tanstack/react-query";
import { ShieldAlert, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { FormStatus } from "../../components/FormStatus";
import { ApiError } from "../../lib/api";
import type { QuarantineAction } from "../../lib/contracts/dataFactory";
import { dataFactoryKeys, decideQuarantineCase, loadQuarantineCase } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { quarantineActionLabel, quarantineActions } from "../../lib/quarantinePresentation";
import { useModalFocus } from "../../lib/useModalFocus";
import { QuarantineCaseDetails } from "./QuarantineCaseDetails";
import { useFactoryOperation } from "./useFactoryOperation";

export function QuarantineDecisionDialog({
  versionId,
  canManage,
  onClose,
  onDecided,
}: {
  versionId: string;
  canManage: boolean;
  onClose: () => void;
  onDecided: () => Promise<void>;
}) {
  useLocale();
  const quarantine = useQuery({
    queryKey: dataFactoryKeys.quarantine(versionId),
    queryFn: ({ signal }) => loadQuarantineCase(versionId, signal),
  });
  const denied = quarantine.error instanceof ApiError && [401, 403].includes(quarantine.error.status);
  const mismatch = Boolean(quarantine.data && quarantine.data.source_version_id !== versionId);
  const data = denied || mismatch ? undefined : quarantine.data,
    actions = data ? quarantineActions(data.quarantine_status) : [];
  const [action, setAction] = useState<QuarantineAction>("hold"),
    [reason, setReason] = useState("");
  const [operationKey, setOperationKey] = useState(() => `quarantine-decision:${crypto.randomUUID()}`);
  const [accepted, setAccepted] = useState<{ action: string; workflowId: string | null } | null>(null);
  const operation = useFactoryOperation(),
    busy = Boolean(operation.busy);
  const dismiss = () => {
    if (!operation.isLocked()) onClose();
  };
  const dialogRef = useModalFocus<HTMLElement>(true, dismiss, { closeOnEscape: !busy });
  useEffect(() => {
    if (actions.length && !actions.includes(action)) setAction(actions[0]);
  }, [action, actions]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (
      !canManage ||
      !data ||
      quarantine.isError ||
      quarantine.isFetching ||
      !actions.includes(action) ||
      reason.trim().length < 3 ||
      reason.trim().length > 500
    )
      return;
    await operation.execute(`quarantine:${versionId}:decision`, "隔离案件处置失败", async (current) => {
      const result = await decideQuarantineCase(versionId, {
        operation_key: operationKey,
        expected_version: data.quarantine_version,
        action,
        reason: reason.trim(),
      });
      if (!current()) return;
      setAccepted({ action: result.action, workflowId: result.workflow_id });
      setReason("");
      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
      await onDecided();
      if (current()) await quarantine.refetch();
    });
  }
  const acceptedLabel = accepted
    ? accepted.action === "rescan"
      ? t("复扫工作流已提交：{id}", { id: accepted.workflowId ?? t("等待运行标识") })
      : t("处置已记录：{action}", { action: quarantineActionLabel(accepted.action) })
    : "";
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel quarantine-dialog"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby="quarantine-dialog-title"
        tabIndex={-1}
      >
        <header>
          <h2 id="quarantine-dialog-title">{t(canManage ? "隔离案件处置" : "隔离案件详情")}</h2>
          <button
            className="icon-button"
            type="button"
            onClick={dismiss}
            disabled={busy}
            title={t("关闭隔离案件")}
            aria-label={t("关闭隔离案件")}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        {quarantine.isPending ? <Spinner label={t("正在读取隔离案件")} /> : null}
        {quarantine.error instanceof Error ? (
          <div className="quarantine-dialog-state">
            <ErrorState message={quarantine.error.message} retry={() => void quarantine.refetch()} />
          </div>
        ) : null}
        {mismatch ? (
          <ErrorState message={t("隔离案件与请求版本不一致")} retry={() => void quarantine.refetch()} />
        ) : null}
        {data ? (
          <form onSubmit={submit}>
            {quarantine.isError ? <p className="field-help">{t("上次读取的隔离案件（非实时）")}</p> : null}
            <QuarantineCaseDetails data={data} />
            {canManage && actions.length ? (
              <fieldset className="source-form-fields" disabled={busy || quarantine.isError || quarantine.isFetching}>
                <label>
                  <span>{t("处置动作")}</span>
                  <select
                    value={action}
                    onChange={(event) => {
                      setAction(event.target.value as QuarantineAction);
                      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
                      operation.clear();
                    }}
                  >
                    {actions.map((item) => (
                      <option key={item} value={item}>
                        {quarantineActionLabel(item)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>{t("处置原因")}</span>
                  <textarea
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    minLength={3}
                    maxLength={500}
                    required
                  />
                </label>
              </fieldset>
            ) : (
              <p className="field-help">
                {t(canManage ? "当前案件状态没有可执行的人工动作。" : "当前账号仅可查看隔离案件与审计历史。")}
              </p>
            )}
            {accepted ? (
              <div className="inline-success" role="status">
                {acceptedLabel}
              </div>
            ) : null}
            <FormStatus
              pending={busy}
              error={operation.error}
              pendingLabel={t(accepted ? "正在刷新隔离案件状态" : "正在提交隔离处置")}
            />
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={dismiss} disabled={busy}>
                {t("关闭")}
              </button>
              {canManage && actions.length ? (
                <button
                  className="primary-button"
                  type="submit"
                  disabled={
                    busy ||
                    quarantine.isError ||
                    quarantine.isFetching ||
                    reason.trim().length < 3 ||
                    reason.trim().length > 500
                  }
                >
                  <ShieldAlert size={15} aria-hidden="true" />
                  {t(busy ? "正在提交" : "提交处置")}
                </button>
              ) : null}
            </div>
          </form>
        ) : null}
      </section>
    </div>
  );
}
