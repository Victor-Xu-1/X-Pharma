import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import { enterpriseKeys, loadEnterprisePlatform } from "../lib/contracts/enterprise";
import { environmentKeys, loadEnvironment } from "../lib/contracts/environment";
import { EnvironmentInstallationPanel } from "./environment/InstallationPanel";
import { PlatformOperationsPanel } from "./environment/PlatformPanel";
import { EnvironmentRuntimePanel } from "./environment/RuntimePanel";
import "./environment/environment.css";

type Tab = "runtime" | "installation" | "operations";
const tabs = [
  { key: "runtime" as const, label: "环境检测" },
  { key: "installation" as const, label: "安装与修复" },
  { key: "operations" as const, label: "运行与发布证据" },
];

export function EnvironmentView() {
  const [tab, setTab] = useState<Tab>("runtime");
  const snapshot = useQuery({ queryKey: environmentKeys.snapshot, queryFn: ({ signal }) => loadEnvironment(signal) });
  const platform = useQuery({
    queryKey: enterpriseKeys.platform,
    queryFn: ({ signal }) => loadEnterprisePlatform(signal),
    enabled: tab === "operations",
  });
  if (snapshot.isError) return <ErrorState message={snapshot.error.message} retry={() => void snapshot.refetch()} />;
  if (!snapshot.data) return <Spinner label="正在检测网关与主机环境" />;
  const environment = snapshot.data;
  return (
    <section className="environment-workbench">
      <div className="enterprise-toolbar">
        <span>
          X-Pharma v{environment.product_version} · {environment.environment} · 状态读取{" "}
          {formatDate(environment.generated_at, true)}
        </span>
        <button
          className="secondary-button"
          type="button"
          disabled={snapshot.isFetching || platform.isFetching}
          onClick={() => {
            void snapshot.refetch();
            if (tab === "operations") void platform.refetch();
          }}
        >
          <RefreshCw size={15} aria-hidden="true" />
          刷新状态
        </button>
      </div>
      <ResearchTabList tabs={tabs} activeTab={tab} onChange={setTab} ariaLabel="环境管理功能" idPrefix="environment" />
      <div role="tabpanel" id={`environment-panel-${tab}`} aria-labelledby={`environment-tab-${tab}`}>
        {tab === "runtime" ? <EnvironmentRuntimePanel environment={environment} /> : null}
        {tab === "installation" ? <EnvironmentInstallationPanel environment={environment} /> : null}
        {tab === "operations" ? (
          platform.isError ? (
            <ErrorState message={platform.error.message} retry={() => void platform.refetch()} />
          ) : platform.data ? (
            <PlatformOperationsPanel platform={platform.data} />
          ) : (
            <Spinner label="正在读取真实运行与发布证据" />
          )
        ) : null}
      </div>
    </section>
  );
}
