import { ShieldAlert } from "lucide-react";
import { formatDate, StatusBadge } from "../../components/common";
import type { QuarantineCase } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { quarantineDecisionLabel, quarantineStatusLabel } from "../../lib/quarantinePresentation";

export function QuarantineCaseDetails({ data }: { data: QuarantineCase }) {
  useLocale();
  return (
    <>
      <dl className="quarantine-case-summary">
        <div>
          <dt>{t("文件")}</dt>
          <dd>{data.file_name}</dd>
        </div>
        <div>
          <dt>{t("状态")}</dt>
          <dd>
            <StatusBadge value={data.quarantine_status} label={quarantineStatusLabel(data.quarantine_status)} />
          </dd>
        </div>
        <div>
          <dt>{t("来源路径")}</dt>
          <dd className="mono-cell">{data.logical_path}</dd>
        </div>
        <div>
          <dt>{t("威胁签名")}</dt>
          <dd className="quarantine-threat">{data.threat_name ?? t("未披露")}</dd>
        </div>
        <div>
          <dt>{t("决策版本")}</dt>
          <dd>v{data.quarantine_version}</dd>
        </div>
        <div>
          <dt>{t("最近变更")}</dt>
          <dd>{formatDate(data.updated_at, true)}</dd>
        </div>
      </dl>
      <div className="quarantine-safety-note" role="note">
        <ShieldAlert size={17} aria-hidden="true" />
        <span>{t("重新扫描只会从恶意文件扫描阶段启动，仍强制经过 ClamAV；不会直接进入解析、AI 治理或检索发布。")}</span>
      </div>
      <section className="quarantine-history" aria-labelledby="quarantine-history-title">
        <h3 id="quarantine-history-title">{t("不可变处置历史")}</h3>
        {data.decisions?.length ? (
          <ol>
            {data.decisions.map((decision) => (
              <li key={decision.id}>
                <span className="quarantine-history-version">v{decision.resulting_version}</span>
                <span>
                  <strong>{quarantineDecisionLabel(decision.action)}</strong>
                  <small>
                    {decision.actor_id} · {formatDate(decision.created_at, true)}
                  </small>
                  <p>{decision.reason}</p>
                </span>
                <StatusBadge
                  value={decision.resulting_status}
                  label={quarantineStatusLabel(decision.resulting_status)}
                />
              </li>
            ))}
          </ol>
        ) : (
          <p className="field-help">{t("尚无处置历史，案件数据不完整，请联系平台管理员。")}</p>
        )}
      </section>
    </>
  );
}
