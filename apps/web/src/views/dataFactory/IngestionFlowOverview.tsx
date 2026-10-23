import { BrainCircuit, FileCheck2, FolderCog, type LucideIcon, ScanSearch, ShieldCheck } from "lucide-react";
import { StatusBadge } from "../../components/common";
import type { IngestionCapabilitiesRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { FactoryDetailsPanel } from "./FactoryDetailsPanel";

function CapabilityStage({
  icon: Icon,
  title,
  detail,
  configured,
}: {
  icon: LucideIcon;
  title: string;
  detail: string;
  configured?: boolean;
}) {
  return (
    <li className={configured === false ? "pending" : undefined}>
      <span className="pipeline-icon">
        <Icon size={18} aria-hidden="true" />
      </span>
      <span>
        <strong>{title}</strong>
        <small>{detail}</small>
      </span>
      <span className="pipeline-capability-label">
        {t(configured === undefined ? "控制步骤" : configured ? "已启用" : "未启用")}
      </span>
    </li>
  );
}

export function IngestionFlowOverview({
  capabilities,
  stale,
}: {
  capabilities: IngestionCapabilitiesRead;
  stale: boolean;
}) {
  useLocale();
  const modelEnabled = capabilities.ai_governance_enabled && capabilities.ai_model_configured;
  return (
    <FactoryDetailsPanel
      title={t("采集与治理流程")}
      summary={
        stale ? (
          t("上次读取")
        ) : (
          <StatusBadge
            value={capabilities.automatic_scheduling_enabled ? "active" : "inactive"}
            label={t(capabilities.automatic_scheduling_enabled ? "调度已启用" : "调度未启用")}
          />
        )
      }
    >
      <p>{t("处理能力说明，不代表某次入库已完成；实际执行结果请查看入库运行记录。")}</p>
      <ol className="pipeline-stages">
        <CapabilityStage
          icon={FolderCog}
          title={t("来源发现")}
          detail={t("官方接口与获授权只读来源")}
          configured={capabilities.automatic_scheduling_enabled}
        />
        <CapabilityStage
          icon={FileCheck2}
          title={t("安全解析")}
          detail={t(capabilities.isolated_parser_enabled ? "隔离解析服务" : "未启用隔离解析服务")}
          configured={capabilities.isolated_parser_enabled}
        />
        <CapabilityStage
          icon={BrainCircuit}
          title={t("结构化治理")}
          detail={
            capabilities.deterministic_governance_enabled
              ? t("官方结构化来源可直接校验")
              : modelEnabled
                ? t("第三方 API · {model}", { model: capabilities.ai_model ?? t("已配置") })
                : t("未启用可用治理链路")
          }
          configured={capabilities.deterministic_governance_enabled || modelEnabled}
        />
        <CapabilityStage
          icon={ShieldCheck}
          title={t("质量审核")}
          detail={t("低置信度进入审核队列；完成情况以审核记录为准")}
        />
        <CapabilityStage icon={ScanSearch} title={t("发布检索")} detail={t("受控发布后，Web 与 MCP 使用同源引用")} />
      </ol>
      {!modelEnabled ? (
        <div className="factory-warning" role="status">
          <BrainCircuit size={17} aria-hidden="true" />
          <span>
            <strong>{t("第三方 LLM API 尚未启用")}</strong>
            {t(
              "非结构化文档的模型事实抽取未启用；已授权的 ClinicalTrials.gov 与 ChEMBL 可走独立确定性治理。全文、OCR 和语义模型仍需各自配置与授权。",
            )}
          </span>
        </div>
      ) : null}
    </FactoryDetailsPanel>
  );
}
