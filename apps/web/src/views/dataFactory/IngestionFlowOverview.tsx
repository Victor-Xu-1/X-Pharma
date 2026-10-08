import { BrainCircuit, FileCheck2, FolderCog, type LucideIcon, ScanSearch, ShieldCheck } from "lucide-react";
import { StatusBadge } from "../../components/common";
import type { IngestionCapabilitiesRead } from "../../lib/generated";
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
        {configured === undefined ? "控制步骤" : configured ? "已启用" : "未启用"}
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
  const modelEnabled = capabilities.ai_governance_enabled && capabilities.ai_model_configured;
  return (
    <FactoryDetailsPanel
      title="采集与治理流程"
      summary={
        stale ? (
          "上次读取"
        ) : (
          <StatusBadge
            value={capabilities.automatic_scheduling_enabled ? "active" : "inactive"}
            label={capabilities.automatic_scheduling_enabled ? "调度已启用" : "调度未启用"}
          />
        )
      }
    >
      <p>处理能力说明，不代表某次入库已完成；实际执行结果请查看入库运行记录。</p>
      <ol className="pipeline-stages">
        <CapabilityStage
          icon={FolderCog}
          title="来源发现"
          detail="官方接口与获授权只读来源"
          configured={capabilities.automatic_scheduling_enabled}
        />
        <CapabilityStage
          icon={FileCheck2}
          title="安全解析"
          detail={capabilities.isolated_parser_enabled ? "隔离解析服务" : "未启用隔离解析服务"}
          configured={capabilities.isolated_parser_enabled}
        />
        <CapabilityStage
          icon={BrainCircuit}
          title="结构化治理"
          detail={
            capabilities.deterministic_governance_enabled
              ? "官方结构化来源可直接校验"
              : modelEnabled
                ? `第三方 API · ${capabilities.ai_model ?? "已配置"}`
                : "未启用可用治理链路"
          }
          configured={capabilities.deterministic_governance_enabled || modelEnabled}
        />
        <CapabilityStage icon={ShieldCheck} title="质量审核" detail="低置信度进入审核队列；完成情况以审核记录为准" />
        <CapabilityStage icon={ScanSearch} title="发布检索" detail="受控发布后，Web 与 MCP 使用同源引用" />
      </ol>
      {!modelEnabled ? (
        <div className="factory-warning" role="status">
          <BrainCircuit size={17} aria-hidden="true" />
          <span>
            <strong>第三方 LLM API 尚未启用</strong>非结构化文档的模型事实抽取未启用；已授权的 ClinicalTrials.gov 与
            ChEMBL 可走独立确定性治理。全文、OCR 和语义模型仍需各自配置与授权。
          </span>
        </div>
      ) : null}
    </FactoryDetailsPanel>
  );
}
