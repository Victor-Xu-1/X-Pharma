import { Copy } from "lucide-react";
import { useState } from "react";
import type {
  EnterpriseApiKeyCatalog,
  EnterpriseApiKeyOperation,
  EnterpriseApiKeySecret,
} from "../../lib/contracts/enterprise";
import { useLocale } from "../../lib/i18n";
import { type EnterpriseAccessMessageKey, enterpriseAccessText as t } from "../../lib/i18n/enterpriseAccess";
import { ModalShell } from "./ModalShell";
import type { ApiKeyAction } from "./types";

export const apiKeyScopeLabels: Record<string, EnterpriseAccessMessageKey> = {
  "mcp:connect": "MCP 连接",
  "entities:read": "实体检索",
  "dossiers:read": "专业档案",
  "targets:read": "靶点情报",
  "activities:read": "活性数据",
  "pipelines:read": "研发管线",
  "structures:read": "化学结构",
  "trials:read": "临床试验",
  "patents:read": "专利情报",
  "deals:read": "交易情报",
  "regulatory:read": "监管情报",
  "epidemiology:read": "流行病学",
  "news:read": "资讯事件",
  "knowledge:read": "知识页面",
  "evidence:read": "证据检索",
  "workspace:export": "受控导出",
};

export function apiKeyScopeLabel(scope: string): string {
  return apiKeyScopeLabels[scope] ? t(apiKeyScopeLabels[scope]) : scope;
}

export function localDateTimeValue(value?: string | null, daysFromNow = 90): string {
  const date = value ? new Date(value) : new Date(Date.now() + daysFromNow * 86_400_000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function ApiKeyActionModal({
  action,
  catalog,
  busy,
  close,
  submit,
}: {
  action: ApiKeyAction;
  catalog: EnterpriseApiKeyCatalog;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseApiKeyOperation) => Promise<void>;
}) {
  useLocale();
  const apiKey = action.kind === "create" ? null : action.apiKey;
  const [name, setName] = useState(apiKey?.name ?? "");
  const [expiresAt, setExpiresAt] = useState(localDateTimeValue(apiKey?.expires_at));
  const [scopes, setScopes] = useState<string[]>(
    action.kind === "create" ? [...catalog.allowed_scopes] : [...(apiKey?.scopes ?? [])],
  );
  const [reason, setReason] = useState("");
  const title =
    action.kind === "create" ? "新建 Agent API 密钥" : action.kind === "rotate" ? "轮换 API 密钥" : "撤销 API 密钥";
  const canSubmit =
    reason.trim().length >= 3 &&
    (action.kind === "revoke" || (name.trim().length > 0 && expiresAt.length > 0 && scopes.length >= 2));

  return (
    <ModalShell title={t(title)} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (action.kind === "create") {
            void submit({
              kind: "create-api-key",
              requestBody: {
                name: name.trim(),
                scopes,
                expires_at: new Date(expiresAt).toISOString(),
                reason: reason.trim(),
              },
            });
          } else if (action.kind === "rotate") {
            void submit({
              kind: "rotate-api-key",
              keyId: action.apiKey.id,
              requestBody: {
                name: name.trim(),
                expires_at: new Date(expiresAt).toISOString(),
                reason: reason.trim(),
              },
            });
          } else {
            void submit({
              kind: "revoke-api-key",
              keyId: action.apiKey.id,
              requestBody: { reason: reason.trim() },
            });
          }
        }}
      >
        {apiKey ? (
          <p className="enterprise-modal-subject">
            {apiKey.name}
            <span className="mono-value">{apiKey.prefix}</span>
          </p>
        ) : null}
        {action.kind !== "revoke" ? (
          <>
            <label>
              {t("密钥名称")}
              <input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              {t("到期时间")}
              <input
                required
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
              <span className="cell-subtitle">
                {t("最长 {days} 天，到期后自动拒绝认证。", { days: catalog.max_ttl_days })}
              </span>
            </label>
          </>
        ) : null}
        {action.kind === "create" ? (
          <fieldset className="enterprise-member-list">
            <legend>{t("授权范围")}</legend>
            {catalog.allowed_scopes.map((scope) => (
              <label key={scope}>
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  disabled={scope === catalog.required_scope}
                  onChange={(event) =>
                    setScopes((current) =>
                      event.target.checked
                        ? [...new Set([...current, scope])]
                        : current.filter((item) => item !== scope),
                    )
                  }
                />
                <span>
                  {apiKeyScopeLabel(scope)}
                  <small className="mono-value">{scope}</small>
                </span>
              </label>
            ))}
          </fieldset>
        ) : null}
        {action.kind === "revoke" ? (
          <p className="inline-warning">{t("撤销后不能重新启用；该密钥及其 API-key 商业主体会立即失效。")}</p>
        ) : null}
        <label>
          {t("变更原因")}
          <textarea
            required
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            {t("取消")}
          </button>
          <button className="primary-button" type="submit" disabled={busy || !canSubmit}>
            {action.kind === "create" ? t("创建密钥") : action.kind === "rotate" ? t("轮换密钥") : t("确认撤销")}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

export function ApiKeySecretModal({ item, close }: { item: EnterpriseApiKeySecret; close: () => void }) {
  useLocale();
  const [copyStatus, setCopyStatus] = useState<EnterpriseAccessMessageKey | null>(null);

  return (
    <ModalShell title={t("立即保存 API 密钥")} close={close}>
      <p className="inline-warning" role="status">
        {t("这是完整密钥唯一一次显示。关闭后平台无法找回，请立即存入获批的密钥管理器。")}
      </p>
      <label>
        {t("API 密钥")}
        <input
          className="mono-value"
          aria-label={t("API 密钥")}
          data-modal-autofocus="true"
          onFocus={(event) => event.currentTarget.select()}
          readOnly
          value={item.secret}
        />
      </label>
      <p className="enterprise-modal-subject">
        {item.name}
        <span className="mono-value">
          {t("密钥 ID：")}
          {item.id}
        </span>
      </p>
      {copyStatus ? <p role="status">{t(copyStatus)}</p> : null}
      <div className="form-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            if (!navigator.clipboard) {
              setCopyStatus("当前浏览器不允许自动复制，请手动选择密钥。");
              return;
            }
            void navigator.clipboard.writeText(item.secret).then(
              () => setCopyStatus("已复制"),
              () => setCopyStatus("复制失败，请手动选择密钥。"),
            );
          }}
        >
          <Copy size={16} />
          {t("复制密钥")}
        </button>
        <button className="primary-button" type="button" onClick={close}>
          {t("已安全保存")}
        </button>
      </div>
    </ModalShell>
  );
}
