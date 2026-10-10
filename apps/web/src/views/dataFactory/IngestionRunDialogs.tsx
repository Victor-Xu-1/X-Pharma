import { CircleStop, RotateCcw } from "lucide-react";
import type { IngestionRun } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { FactoryReasonDialog } from "./FactoryReasonDialog";

type Props = {
  run: IngestionRun;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (key: string, reason: string) => Promise<void>;
};

export function ReplayRunDialog({ run, ...operation }: Props) {
  useLocale();
  return (
    <FactoryReasonDialog
      {...operation}
      title={t("重放入库运行")}
      titleId="replay-run-title"
      description={t("将按当前数据源治理配置重新扫描；原运行与发现项保持不变，新运行会单独记录并写入审计日志。")}
      operationKeyPrefix={`ingestion-replay:${run.id}`}
      reasonLabel={t("重放原因")}
      pendingLabel={t("正在提交重放请求")}
      confirmLabel={t("确认重放")}
      pendingConfirmLabel={t("正在提交")}
      icon={RotateCcw}
    >
      <label>
        <span>{t("原工作流")}</span>
        <input value={run.workflow_id} readOnly className="mono-cell" />
      </label>
    </FactoryReasonDialog>
  );
}

export function CancelRunDialog({ run, ...operation }: Props) {
  useLocale();
  return (
    <FactoryReasonDialog
      {...operation}
      title={t("取消入库运行")}
      titleId="cancel-run-title"
      description={t(
        "取消请求只发送到该运行绑定的 Temporal 执行。已完成的不可变快照会保留，后续阶段将在安全检查点停止。",
      )}
      operationKeyPrefix={`ingestion-cancel:${run.id}`}
      reasonLabel={t("取消原因")}
      pendingLabel={t("正在提交取消请求")}
      confirmLabel={t("确认取消")}
      pendingConfirmLabel={t("正在取消")}
      cancelLabel={t("返回")}
      icon={CircleStop}
      danger
    >
      <label>
        <span>{t("运行关联标识")}</span>
        <input value={run.workflow_id} readOnly className="mono-cell" />
      </label>
    </FactoryReasonDialog>
  );
}
