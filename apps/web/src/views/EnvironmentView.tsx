import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import { enterpriseKeys, loadEnterprisePlatform } from "../lib/contracts/enterprise";
import { environmentKeys, loadEnvironment } from "../lib/contracts/environment";
import { EnvironmentInstallationPanel } from "./environment/InstallationPanel";
import { PlatformOperationsPanel } from "./environment/PlatformPanel";
import { EnvironmentProbeTable } from "./environment/ProbeTable";

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
        {tab === "runtime" ? (
          <>
            <section>
              <header>
                <h2>应用运行环境</h2>
                <p>网关进程的实际版本，不代表主机或其他容器已经健康。</p>
              </header>
              <EnvironmentProbeTable probes={environment.runtime} label="网关依赖版本" />
            </section>
            <section>
              <header>
                <h2>主机与项目依赖</h2>
                <p>{environment.host_detail}</p>
              </header>
              {environment.host ? (
                <>
                  <p>
                    主机检测 {formatDate(environment.host.generated_at, true)} · 源码{" "}
                    {environment.host.revision.slice(0, 12)} ·{" "}
                    {environment.host.clean_source ? "源码干净" : "存在未提交变更"} · 可用空间{" "}
                    {(environment.host.disk_free_bytes / 1024 ** 3).toFixed(1)} GiB
                  </p>
                  <EnvironmentProbeTable probes={environment.host.probes} label="主机依赖版本" />
                  {environment.host.latest_install ? (
                    <p role="status">
                      最近安装：{environment.host.latest_install.recipe_id} ·{" "}
                      {environment.host.latest_install.status === "succeeded"
                        ? "成功"
                        : environment.host.latest_install.status === "running"
                          ? "执行中"
                          : "失败"}{" "}
                      · {environment.host.latest_install.detail}
                      {" · "}
                      {environment.host.latest_install.revision
                        ? `安装时源码 ${environment.host.latest_install.revision.slice(0, 12)}`
                        : "旧记录未绑定源码，不能作为当前源码的安装证明"}
                    </p>
                  ) : null}
                </>
              ) : (
                <p role="status">尚无有效的主机报告。可在“安装与修复”查看接入步骤。</p>
              )}
            </section>
          </>
        ) : null}
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
