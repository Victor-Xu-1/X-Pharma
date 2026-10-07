import { BrainCircuit, Pencil, Plus, Star, TestTube2 } from "lucide-react";
import { useState } from "react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseLLMProvider, EnterpriseLLMProviderOperation } from "../../lib/contracts/enterprise";
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
  const activeProviders = providers.filter((provider) => provider.active).sort((a, b) => a.priority - b.priority);
  const primaryProvider = activeProviders.find((provider) => provider.priority === 0) ?? activeProviders[0];
  const fallbackProviders = primaryProvider
    ? activeProviders.filter((provider) => provider.id !== primaryProvider.id)
    : [];
  return (
    <div className="enterprise-llm-settings">
      <div className="section-toolbar">
        <span>
          <BrainCircuit size={16} /> {providers.length} 个远程模型供应商 · 按顺序自动故障转移
        </span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          增加 LLM
        </button>
      </div>
      <fieldset className="enterprise-modal-subject" aria-label={"\u5f53\u524d LLM \u8c03\u7528\u987a\u5e8f"}>
        <legend>{"\u5f53\u524d\u8c03\u7528\u987a\u5e8f"}</legend>
        {primaryProvider ? (
          <span>
            {"\u4e3b\u6a21\u578b\uff1a"}
            {primaryProvider.model}
            {fallbackProviders.length
              ? ` \u2192 \u5907\u7528\uff1a${fallbackProviders.map((provider) => provider.model).join(" \u2192 ")}`
              : " \u00b7 \u5c1a\u672a\u914d\u7f6e\u5907\u7528\u6a21\u578b"}
          </span>
        ) : (
          <span>
            {
              "\u5c1a\u672a\u542f\u7528\u6a21\u578b\u3002\u8bf7\u5148\u589e\u52a0 MiMo v2.5\uff0c\u518d\u589e\u52a0 GLM 5.2 \u4f5c\u4e3a\u5907\u7528\u3002"
            }
          </span>
        )}
        <span>{`\u4e3b\u6a21\u578b\u53d1\u751f\u8d85\u65f6\u3001 408\u3001 429\u3001 5xx \u6216\u7f51\u7edc\u6545\u969c\u65f6\uff0c\u7cfb\u7edf\u4f1a\u6309\u987a\u5e8f\u4f7f\u7528\u540e\u7eed\u6a21\u578b\u3002`}</span>
      </fieldset>
      {providers.length ? (
        <ScrollableTableRegion className="enterprise-table" ariaLabel="LLM 供应商顺序滚动区域">
          <table aria-label="LLM 供应商顺序">
            <thead>
              <tr>
                <th>顺序</th>
                <th>供应商与模型</th>
                <th>协议</th>
                <th>超时策略</th>
                <th>连接状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => (
                <tr key={provider.id}>
                  <td>
                    {provider.priority === 0 && provider.active ? (
                      <span className="llm-primary-label">
                        <Star size={14} /> 主模型
                      </span>
                    ) : (
                      `备用 ${provider.priority}`
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
                    <span className="cell-subtitle">思考模式：{provider.thinking_mode}</span>
                  </td>
                  <td>
                    {provider.request_timeout_seconds}s × {provider.request_attempts}
                    <span className="cell-subtitle">
                      最大输出 {provider.max_output_tokens_per_segment.toLocaleString()} tokens
                    </span>
                  </td>
                  <td>
                    <StatusBadge value={provider.active ? "active" : "disabled"} />
                    <span className="cell-subtitle">
                      {provider.last_test_status
                        ? `${provider.last_test_status === "passed" ? "测试通过" : "测试失败"} · ${formatDate(provider.last_tested_at, true)}`
                        : "尚未测试"}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title="测试连接"
                        aria-label={`测试 ${provider.name} 连接`}
                        onClick={() => onTest(provider)}
                        disabled={Boolean(busy) || !provider.active}
                      >
                        <TestTube2 size={16} />
                      </button>
                      {provider.priority !== 0 ? (
                        <button
                          className="icon-button"
                          type="button"
                          title="设为主模型"
                          aria-label={`将 ${provider.name} 设为主模型`}
                          onClick={() => onPrimary(provider)}
                          disabled={Boolean(busy) || !provider.active}
                        >
                          <Star size={16} />
                        </button>
                      ) : null}
                      <button
                        className="icon-button"
                        type="button"
                        title="编辑模型设置"
                        aria-label={`编辑 ${provider.name}`}
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
          title="尚未配置远程模型"
          detail="增加经过批准的 OpenAI-compatible HTTPS 模型；保存后，新治理任务会按这里的顺序调用。"
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
      <ModalShell title={`将 ${action.provider.name} 设为主模型`} close={close}>
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
          <p>保存后，新启动的 AI 入库任务会先调用该模型；超时或可重试故障时再调用后续备用模型。</p>
          <label>
            调整原因
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} required />
          </label>
          <div className="modal-actions">
            <button className="secondary-button" type="button" onClick={close} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              {busy ? "切换中" : "确认切换"}
            </button>
          </div>
        </form>
      </ModalShell>
    );
  }

  return (
    <ModalShell title={action.kind === "create" ? "增加 LLM" : `编辑 ${action.provider.name}`} close={close}>
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
          <fieldset className="enterprise-modal-subject" aria-label={"LLM \u63a8\u8350\u914d\u7f6e"}>
            <legend>{"\u5feb\u901f\u914d\u7f6e\u63a8\u8350\u6a21\u578b"}</legend>
            <span>
              {
                "\u5efa\u8bae\u5148\u4fdd\u5b58 MiMo v2.5 \u4f5c\u4e3a\u4e3b\u6a21\u578b\uff0c\u518d\u4fdd\u5b58 GLM 5.2 \u4f5c\u4e3a\u8d85\u65f6\u5907\u7528\u6a21\u578b\u3002"
              }
            </span>
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={() => applyPreset("mimo")} disabled={busy}>
                {"\u4f7f\u7528 MiMo v2.5 \u4e3b\u6a21\u578b\u9884\u8bbe"}
              </button>
              <button className="secondary-button" type="button" onClick={() => applyPreset("glm")} disabled={busy}>
                {"\u4f7f\u7528 GLM 5.2 \u5907\u7528\u9884\u8bbe"}
              </button>
            </div>
          </fieldset>
        ) : null}
        <div className="form-grid">
          <label>
            供应商名称
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
          </label>
          <label>
            模型 ID
            <input value={model} onChange={(event) => setModel(event.target.value)} maxLength={500} required />
          </label>
          <label className="full-span">
            API 根地址
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
              placeholder={provider ? "留空则保持现有密钥" : "输入供应商 API Key"}
              required={!provider}
            />
          </label>
          <label>
            响应协议
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
            思考模式
            <select
              value={thinkingMode}
              onChange={(event) => setThinkingMode(event.target.value as typeof thinkingMode)}
            >
              <option value="disabled">关闭</option>
              <option value="provider_default">供应商默认</option>
              <option value="enabled">开启</option>
            </select>
          </label>
          <label>
            单次超时（秒）
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
            尝试次数
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
            最大输出 tokens
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
            在提示词中附带 Schema
          </label>
          {provider ? (
            <label className="checkbox-field">
              <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
              启用此供应商
            </label>
          ) : null}
        </div>
        <label>
          变更原因
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
            取消
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
            {busy ? "保存中" : "保存设置"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
