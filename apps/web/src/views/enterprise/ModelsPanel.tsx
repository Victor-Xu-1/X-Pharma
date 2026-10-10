import { BrainCircuit, Pencil, Plus, Star, TestTube2 } from "lucide-react";
import { useState } from "react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseLLMProvider, EnterpriseLLMProviderOperation } from "../../lib/contracts/enterprise";
import { useLocale } from "../../lib/i18n";
import { enterpriseModelText as t } from "../../lib/i18n/enterpriseModels";
import { ModalShell } from "./ModalShell";
import type { LLMAction, LLMProviderPreset } from "./types";

export const llmProviderPresets: Record<
  LLMProviderPreset,
  {
    name: string;
    baseUrl: string;
    model: string;
    attempts: number;
  }
> = {
  mimo: {
    name: "mimo",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
    model: "mimo-v2.5",
    attempts: 2,
  },
  glm: {
    name: "glm",
    baseUrl: "https://chatapi.weixin.qq.com/openai/v1",
    model: "GLM-5.2",
    attempts: 1,
  },
};

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
              ? " → " + t("备用：") + fallbackProviders.map((provider) => provider.model).join(" → ")
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

export function LLMProviderModal({
  action,
  busy,
  close,
  submit,
}: {
  action: LLMAction;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseLLMProviderOperation) => Promise<void>;
}) {
  useLocale();
  const provider = action.kind === "create" ? null : action.provider;
  const [name, setName] = useState(provider?.name ?? "");
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? "");
  const [model, setModel] = useState(provider?.model ?? "");
  const [apiKey, setApiKey] = useState("");
  const [active, setActive] = useState(provider?.active ?? true);
  const [responseMode, setResponseMode] = useState(provider?.response_format_mode ?? "prompt_only");
  const [thinkingMode, setThinkingMode] = useState(provider?.thinking_mode ?? "disabled");
  const [includeSchema, setIncludeSchema] = useState(provider?.include_schema_in_prompt ?? true);
  const [maxOutputTokens, setMaxOutputTokens] = useState(provider?.max_output_tokens_per_segment ?? 16_384);
  const [timeoutSeconds, setTimeoutSeconds] = useState(provider?.request_timeout_seconds ?? 120);
  const [attempts, setAttempts] = useState(provider?.request_attempts ?? 2);
  const [reason, setReason] = useState("");

  const applyPreset = (preset: LLMProviderPreset) => {
    const values = llmProviderPresets[preset];
    setName(values.name);
    setBaseUrl(values.baseUrl);
    setModel(values.model);
    setResponseMode("prompt_only");
    setThinkingMode("disabled");
    setIncludeSchema(true);
    setMaxOutputTokens(16_384);
    setTimeoutSeconds(120);
    setAttempts(values.attempts);
    setApiKey("");
  };

  if (action.kind === "primary") {
    return (
      <ModalShell title={t("将 {name} 设为主模型", { name: action.provider.name })} close={close}>
        <form
          className="stacked-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit({
              kind: "make-llm-primary",
              providerId: action.provider.id,
              requestBody: { expected_version: action.provider.version, reason },
            });
          }}
        >
          <p>{t("保存后，新启动的 AI 入库任务会先调用该模型；超时或可重试故障时再调用后续备用模型。")}</p>
          <label>
            {t("调整原因")}
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} required />
          </label>
          <div className="modal-actions">
            <button className="secondary-button" type="button" onClick={close} disabled={busy}>
              {t("取消")}
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              {busy ? t("切换中") : t("确认切换")}
            </button>
          </div>
        </form>
      </ModalShell>
    );
  }

  return (
    <ModalShell
      title={action.kind === "create" ? t("增加 LLM") : t("编辑 {name}", { name: action.provider.name })}
      close={close}
    >
      <form
        className="stacked-form llm-provider-form"
        onSubmit={(event) => {
          event.preventDefault();
          const common = {
            name,
            base_url: baseUrl,
            model,
            response_format_mode: responseMode,
            thinking_mode: thinkingMode,
            include_schema_in_prompt: includeSchema,
            max_output_tokens_per_segment: maxOutputTokens,
            request_timeout_seconds: timeoutSeconds,
            request_attempts: attempts,
            reason,
          };
          const operation: EnterpriseLLMProviderOperation =
            action.kind === "create"
              ? { kind: "create-llm-provider", requestBody: { ...common, api_key: apiKey } }
              : {
                  kind: "update-llm-provider",
                  providerId: action.provider.id,
                  requestBody: {
                    ...common,
                    expected_version: action.provider.version,
                    api_key: apiKey || null,
                    active,
                  },
                };
          void submit(operation);
        }}
      >
        {action.kind === "create" ? (
          <fieldset className="enterprise-modal-subject" aria-label={t("已有模型预设")}>
            <legend>{t("已有模型预设")}</legend>
            <span>{t("预设只填入已有配置，不保证当前可用；请核对供应商授权并测试连接。")}</span>
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={() => applyPreset("mimo")} disabled={busy}>
                {t("使用 MiMo v2.5 预设")}
              </button>
              <button className="secondary-button" type="button" onClick={() => applyPreset("glm")} disabled={busy}>
                {t("使用 GLM 5.2 预设")}
              </button>
            </div>
          </fieldset>
        ) : null}
        <div className="form-grid">
          <label>
            {t("供应商名称")}
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
          </label>
          <label>
            {t("模型 ID")}
            <input value={model} onChange={(event) => setModel(event.target.value)} maxLength={500} required />
          </label>
          <label className="full-span">
            {t("API 根地址")}
            <input
              type="url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://provider.example/v1"
              required
            />
          </label>
          <label className="full-span">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="new-password"
              placeholder={provider ? t("留空则保持现有密钥") : t("输入供应商 API Key")}
              required={!provider}
            />
          </label>
          <label>
            {t("响应协议")}
            <select
              value={responseMode}
              onChange={(event) => setResponseMode(event.target.value as typeof responseMode)}
            >
              <option value="prompt_only">Prompt JSON Schema</option>
              <option value="json_object">JSON Object</option>
              <option value="json_schema">JSON Schema</option>
            </select>
          </label>
          <label>
            {t("思考模式")}
            <select
              value={thinkingMode}
              onChange={(event) => setThinkingMode(event.target.value as typeof thinkingMode)}
            >
              <option value="disabled">{t("关闭")}</option>
              <option value="provider_default">{t("供应商默认")}</option>
              <option value="enabled">{t("开启")}</option>
            </select>
          </label>
          <label>
            {t("单次超时（秒）")}
            <input
              type="number"
              min={1}
              max={600}
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
              required
            />
          </label>
          <label>
            {t("尝试次数")}
            <input
              type="number"
              min={1}
              max={8}
              value={attempts}
              onChange={(event) => setAttempts(Number(event.target.value))}
              required
            />
          </label>
          <label>
            {t("最大输出 tokens")}
            <input
              type="number"
              min={256}
              max={131072}
              value={maxOutputTokens}
              onChange={(event) => setMaxOutputTokens(Number(event.target.value))}
              required
            />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={includeSchema}
              onChange={(event) => setIncludeSchema(event.target.checked)}
            />
            {t("在提示词中附带 Schema")}
          </label>
          {provider ? (
            <label className="checkbox-field">
              <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
              {t("启用此供应商")}
            </label>
          ) : null}
        </div>
        <label>
          {t("变更原因")}
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            minLength={3}
            maxLength={500}
            required
          />
        </label>
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={close} disabled={busy}>
            {t("取消")}
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={
              busy ||
              !name.trim() ||
              !baseUrl.trim() ||
              !model.trim() ||
              (!provider && !apiKey) ||
              reason.trim().length < 3
            }
          >
            {busy ? t("保存中") : t("保存设置")}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
