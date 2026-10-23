import { RotateCcw } from "lucide-react";
import { useState } from "react";
import type { SourceVersionReplayStage } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { FactoryReasonDialog } from "./FactoryReasonDialog";

const stageLabels = {
  malware_scan: "安全扫描",
  parse: "文档解析",
  governance: "AI 治理",
  retrieval: "检索投影",
} as const;
export function versionReplayStageLabel(stage: string): string {
  return Object.hasOwn(stageLabels, stage) ? t(stageLabels[stage as keyof typeof stageLabels]) : stage;
}

export function ReplayVersionDialog({
  versionNumber,
  errorCode,
  stages,
  onConfirm,
  ...operation
}: {
  versionNumber: number;
  errorCode: string | null;
  stages: SourceVersionReplayStage[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (key: string, fromStage: SourceVersionReplayStage, reason: string) => Promise<void>;
}) {
  useLocale();
  const [fromStage, setFromStage] = useState<SourceVersionReplayStage>(stages.at(-1) ?? "malware_scan");
  return (
    <FactoryReasonDialog
      {...operation}
      title={t("重放源版本 {number}", { number: versionNumber })}
      titleId="replay-version-title"
      description={
        <>
          {t("恢复只复用已成功且仍可核验的前序产物，并从所选阶段重置后续状态。当前失败代码：")}{" "}
          <span className="mono-cell">{errorCode ?? t("无（阶段状态失败）")}</span>
        </>
      }
      operationKeyPrefix="source-version-replay"
      reasonLabel={t("重放原因")}
      pendingLabel={t("正在提交版本重放请求")}
      confirmLabel={t("确认重放")}
      pendingConfirmLabel={t("正在提交")}
      icon={RotateCcw}
      onConfirm={async (key, reason) => {
        if (stages.includes(fromStage) && Object.hasOwn(stageLabels, fromStage))
          await onConfirm(key, fromStage, reason);
      }}
    >
      <label>
        <span>{t("恢复起点")}</span>
        <select
          disabled={operation.busy}
          value={fromStage}
          onChange={(event) => setFromStage(event.target.value as SourceVersionReplayStage)}
        >
          {stages.map((stage) => (
            <option key={stage} value={stage}>
              {versionReplayStageLabel(stage)}
            </option>
          ))}
        </select>
      </label>
    </FactoryReasonDialog>
  );
}
