import { Plus, RefreshCw } from "lucide-react";
import { EmptyState } from "../../components/common";
import type { DataSource, DataSourceReadiness, IngestionCapabilities } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import type { User } from "../../lib/types";
import { type FactorySourceAction, FactorySourceCard } from "./FactorySourceCard";

export function FactorySourcesPanel({
  sources,
  readiness,
  capabilities,
  busy,
  role,
  onCreate,
  onEdit,
  onAction,
  onRefresh,
}: {
  sources: readonly DataSource[];
  readiness: readonly DataSourceReadiness[];
  capabilities?: IngestionCapabilities;
  busy: boolean;
  role: User["role"];
  onCreate: () => void;
  onEdit: (source: DataSource) => void;
  onAction: (source: DataSource, action: FactorySourceAction) => void;
  onRefresh: () => void;
}) {
  useLocale();
  const connect = (
    <button
      className={sources.length ? "primary-button" : "secondary-button"}
      type="button"
      disabled={busy}
      onClick={onCreate}
    >
      <Plus size={16} />
      {t("接入自动数据源")}
    </button>
  );
  return (
    <section>
      <div className="section-header">
        <div>
          <h2>{t("自动数据源")}</h2>
          <p>{t("受管目录、对象存储与授权数据接口按计划自动增量同步")}</p>
        </div>
        <div className="section-actions">
          <button
            className="icon-button"
            type="button"
            disabled={busy}
            onClick={onRefresh}
            title={t("刷新")}
            aria-label={t("刷新数据工厂")}
          >
            <RefreshCw size={17} />
          </button>
          {role === "admin" && sources.length > 0 ? connect : null}
        </div>
      </div>
      {sources.length ? (
        <div className="source-list">
          {sources.map((source) => (
            <FactorySourceCard
              key={source.id}
              source={source}
              readiness={readiness.find((item) => item.source_id === source.id)}
              capabilities={capabilities}
              busy={busy}
              editable={role === "admin"}
              onAction={onAction}
              onEdit={onEdit}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title={t("尚未接入自动数据源")}
          detail={t("接入固定只读目录或授权数据接口后，调度器会持续发现新增和变更文件。")}
        >
          {role === "admin" ? connect : null}
        </EmptyState>
      )}
    </section>
  );
}
