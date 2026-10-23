import { factoryText as t } from "../../lib/i18n/dataFactory";

const guidance = {
  owner: "请指定可追责的数据负责人",
  authorization_scopes: "请登记至少一个有效的来源授权范围",
  authorization_window: "请检查来源授权的生效与结束时间",
  authorization_not_yet_valid: "来源授权尚未生效，请检查生效时间",
  authorization_expired: "来源授权已过期，请更新授权",
  authorization_expiring: "来源授权即将到期，请及时续期",
  data_classification: "请选择有效的数据分级",
  connector: "当前数据源类型没有可用连接器",
  connector_configuration: "连接器配置未通过，请检查来源地址与抓取参数",
  credential_ref: "请绑定已托管的凭据引用",
  dataset: "目标数据集未登记或已停用",
  license_policy: "目标数据集授权策略无效或当前不可交付",
  delivery_channels: "数据集授权未同时覆盖 Web 与 MCP",
} as const;
const states = {
  ready: "就绪",
  disabled: "已停用",
  paused: "已暂停",
  unavailable: "来源不可用",
  pending: "等待首次成功",
  syncing: "正在同步",
  stale: "已过时",
  blocked: "配置受阻",
} as const;

export function sourceReadinessGuidance(check: { code: string; message: string }, freshnessAge: number | null): string {
  if (check.code === "freshness") return t(freshnessAge === null ? "尚未完成首次扫描" : "数据源已超过更新时效目标");
  return Object.hasOwn(guidance, check.code) ? t(guidance[check.code as keyof typeof guidance]) : check.message;
}

/** Omit only exact application-owned boilerplate; retain variable/provider diagnostics. */
export function sourceReadinessRawDiagnostic(
  check: { code: string; message: string },
  freshnessAge: number | null,
): string | null {
  if (!Object.hasOwn(guidance, check.code) && check.code !== "freshness") return null;
  if (
    check.code === "freshness" &&
    check.message ===
      (freshnessAge === null
        ? "Source has not completed its first scan"
        : `Source is stale by policy (${freshnessAge}s old)`)
  )
    return null;
  if (check.code === "owner" && check.message === "A named accountable data owner is required") return null;
  return check.message;
}

export function sourceOperationalLabel(value: string): string {
  return Object.hasOwn(states, value) ? t(states[value as keyof typeof states]) : value;
}
