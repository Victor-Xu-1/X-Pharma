import { BrainCircuit, Pencil, Plus, Star, TestTube2 } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseLLMProvider } from "../../lib/contracts/enterprise";
import { useLocale } from "../../lib/i18n";
import { enterpriseModelText as t } from "../../lib/i18n/enterpriseModels";

export function LLMProvidersPanel({
  providers,
  busy,
  onCreate,
  onEdit,
  onPrimary,
  onTest,
}: {
  providers: EnterpriseLLMProvider[];
  busy: string;
  onCreate: () => void;
  onEdit: (provider: EnterpriseLLMProvider) => void;
  onPrimary: (provider: EnterpriseLLMProvider) => void;
  onTest: (provider: EnterpriseLLMProvider) => void;
}) {
  useLocale();
  const activeProviders = providers.filter((provider) => provider.active).sort((a, b) => a.priority - b.priority);
  const primaryProvider = activeProviders.find((provider) => provider.priority === 0) ?? activeProviders[0];
  const fallbackProviders = primaryProvider
    ? activeProviders.filter((provider) => provider.id !== primaryProvider.id)
    : [];
  return (
    <div className="enterprise-llm-settings">
      <div className="section-toolbar">
        <span>
          <BrainCircuit size={16} /> {t("{count} 个远程模型供应商", { count: providers.length })} ·{" "}
          {t("按顺序自动故障转移")}
        </span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          {t("增加 LLM")}
        </button>
      </div>
      <fieldset className="enterprise-modal-subject" aria-label={t("当前 LLM 调用顺序")}>
        <legend>{t("当前调用顺序")}</legend>
        {primaryProvider ? (
          <span>
            {t("主模型：")}
            {primaryProvider.model}
            {fallbackProviders.length
              ? ` → ${t("备用：")}${fallbackProviders.map((provider) => provider.model).join(" → ")}`
              : t(" · 尚未配置备用模型")}
          </span>
        ) : (
          <span>{t("尚未启用模型。请先配置已获批的模型供应商。")}</span>
        )}
        <span>{t("主模型发生超时、408、429、5xx 或网络故障时，系统会按顺序使用后续模型。")}</span>
      </fieldset>
      {providers.length ? (
        <ScrollableTableRegion className="enterprise-table" ariaLabel={t("LLM 供应商顺序滚动区域")}>
          <table aria-label={t("LLM 供应商顺序")}>
            <thead>
              <tr>
                <th>{t("顺序")}</th>
                <th>{t("供应商与模型")}</th>
                <th>{t("协议")}</th>
                <th>{t("超时策略")}</th>
                <th>{t("连接状态")}</th>
                <th aria-label={t("操作")} />
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => (
                <tr key={provider.id}>
                  <td>
                    {provider.id === primaryProvider?.id && provider.active ? (
                      <span className="llm-primary-label">
                        <Star size={14} /> {t("主模型")}
                      </span>
                    ) : (
                      t("备用 {priority}", { priority: provider.priority })
                    )}
                  </td>
                  <td>
                    <strong>{provider.name}</strong>
                    <span className="cell-subtitle">
                      {provider.model} · Key {provider.api_key_fingerprint}
                    </span>
                    <span className="cell-subtitle mono-value">{provider.base_url}</span>
                  </td>
                  <td>
                    {provider.response_format_mode}
                    <span className="cell-subtitle">
                      {t("思考模式：")}
                      {provider.thinking_mode}
                    </span>
                  </td>
                  <td>
                    {provider.request_timeout_seconds}s × {provider.request_attempts}
                    <span className="cell-subtitle">
                      {t("最大输出 {count} tokens", { count: provider.max_output_tokens_per_segment })}
                    </span>
                  </td>
                  <td>
                    <StatusBadge value={provider.active ? "active" : "disabled"} />
                    <span className="cell-subtitle">
                      {provider.last_test_status
                        ? `${provider.last_test_status === "passed" ? t("测试通过") : provider.last_test_status === "failed" ? t("测试失败") : provider.last_test_status} · ${formatDate(provider.last_tested_at, true)}`
                        : t("尚未测试")}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title={t("测试连接")}
                        aria-label={t("测试 {name} 连接", { name: provider.name })}
                        onClick={() => onTest(provider)}
                        disabled={Boolean(busy) || !provider.active}
                      >
                        <TestTube2 size={16} />
                      </button>
                      {provider.priority !== 0 ? (
                        <button
                          className="icon-button"
                          type="button"
                          title={t("设为主模型")}
                          aria-label={t("将 {name} 设为主模型", { name: provider.name })}
                          onClick={() => onPrimary(provider)}
                          disabled={Boolean(busy) || !provider.active}
                        >
                          <Star size={16} />
                        </button>
                      ) : null}
                      <button
                        className="icon-button"
                        type="button"
                        title={t("编辑模型设置")}
                        aria-label={t("编辑 {name}", { name: provider.name })}
                        onClick={() => onEdit(provider)}
                        disabled={Boolean(busy)}
                      >
                        <Pencil size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <EmptyState
          title={t("尚未配置远程模型")}
          detail={t("增加经过批准的 OpenAI-compatible HTTPS 模型；保存后，新治理任务会按这里的顺序调用。")}
        />
      )}
    </div>
  );
}
