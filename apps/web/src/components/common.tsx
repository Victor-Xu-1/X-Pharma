import { CircleAlert, Inbox, LockKeyhole, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { formattingLocale, getLocale, type MessageKey, t, uiFeedback, useLocale } from "../lib/i18n";

export function Spinner({ label = t("加载中"), cancel }: { label?: string; cancel?: () => void }) {
  useLocale();
  return (
    <div className="state-message" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
      {cancel ? (
        <button className="text-button" type="button" onClick={cancel}>
          {t("取消查询")}
        </button>
      ) : null}
    </div>
  );
}

export function CancelledState({ retry }: { retry: () => void }) {
  useLocale();
  return (
    <div className="state-message" role="status">
      <strong>{t("查询已取消")}</strong>
      <span>{t("当前查询已停止，筛选条件仍然保留。")}</span>
      <button className="text-button" type="button" onClick={retry}>
        {t("重新查询")}
      </button>
    </div>
  );
}

export function EmptyState({ title, detail, children }: { title: string; detail?: string; children?: ReactNode }) {
  useLocale();
  return (
    <div className="state-message empty-state" role="status" aria-live="polite" aria-atomic="true">
      <span className="state-icon">
        <Inbox size={25} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <strong>{title}</strong>
      {detail ? <span>{detail}</span> : null}
      {children}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  useLocale();
  return (
    <div className="state-message error-state" role="alert">
      <span className="state-icon">
        <CircleAlert size={25} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <strong>{t("数据加载失败")}</strong>
      <span>{uiFeedback(message)}</span>
      {retry ? (
        <button className="text-button" type="button" onClick={retry}>
          {t("重试")}
        </button>
      ) : null}
    </div>
  );
}

export function AccessDeniedState({
  onReturn,
  actionLabel = t("返回工作台"),
}: {
  onReturn: () => void;
  actionLabel?: string;
}) {
  useLocale();
  return (
    <div className="state-message error-state" role="alert">
      <span className="state-icon">
        <LockKeyhole size={25} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <strong>{t("无权访问该工作区")}</strong>
      <span>{t("当前企业角色没有此功能的访问权限。")}</span>
      <button className="text-button" type="button" onClick={onReturn}>
        {actionLabel}
      </button>
    </div>
  );
}

function errorStatus(error: unknown): number | null {
  if (!error || typeof error !== "object" || !("status" in error)) return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}

export function QueryRefreshButton({ refreshing, onRefresh }: { refreshing: boolean; onRefresh: () => void }) {
  useLocale();
  return (
    <button
      className="secondary-button"
      type="button"
      disabled={refreshing}
      onClick={onRefresh}
      title={t("使用当前筛选重新读取最新结果")}
      aria-label={t("刷新当前结果")}
    >
      <RefreshCw size={15} aria-hidden="true" />
      {refreshing ? t("刷新中") : t("刷新")}
    </button>
  );
}

function QueryPermissionState({ retry }: { retry: () => void }) {
  useLocale();
  return (
    <div className="state-message error-state" role="alert">
      <strong>{t("当前账号无权读取这组结果")}</strong>
      <span>{t("数据授权或企业角色可能已经变更。现有结果不会继续显示。")}</span>
      <button className="text-button" type="button" onClick={retry}>
        {t("重新校验权限")}
      </button>
    </div>
  );
}

function QueryRefreshCancelledState({ retry, dismiss }: { retry: () => void; dismiss: () => void }) {
  useLocale();
  return (
    <div className="state-message" role="status">
      <strong>{t("刷新已取消")}</strong>
      <span>{t("筛选条件和上次成功结果均已保留。")}</span>
      <button className="text-button" type="button" onClick={retry}>
        {t("重新刷新")}
      </button>
      <button className="text-button" type="button" onClick={dismiss}>
        {t("关闭提示")}
      </button>
    </div>
  );
}

function QueryPartialDataState({ message, retry }: { message: string; retry: () => void }) {
  useLocale();
  return (
    <div className="state-message error-state" role="alert">
      <strong>{t("最新结果刷新失败")}</strong>
      <span>{t("{message}；当前仍显示上次成功结果。", { message: uiFeedback(message) })}</span>
      <button className="text-button" type="button" onClick={retry}>
        {t("重新刷新")}
      </button>
    </div>
  );
}

export function ProfessionalQueryState({
  dataAvailable,
  enabled = true,
  isFetching,
  isCancelled,
  error,
  loadingLabel,
  fallbackError,
  onCancel,
  onRetry,
  onDismissCancellation,
  idle,
  children,
}: {
  dataAvailable: boolean;
  enabled?: boolean;
  isFetching: boolean;
  isCancelled: boolean;
  error: unknown;
  loadingLabel: string;
  fallbackError: string;
  onCancel: () => void;
  onRetry: () => void;
  onDismissCancellation: () => void;
  idle?: ReactNode;
  children?: ReactNode;
}) {
  useLocale();
  if (errorStatus(error) === 403) return <QueryPermissionState retry={onRetry} />;

  if (!dataAvailable) {
    if (isFetching) return <Spinner label={loadingLabel} cancel={onCancel} />;
    if (isCancelled) return <CancelledState retry={onRetry} />;
    if (error) return <ErrorState message={errorMessage(error, fallbackError)} retry={onRetry} />;
    if (!enabled) return <>{idle}</>;
    return null;
  }

  return (
    <>
      {isFetching ? (
        <Spinner label={t("正在刷新{label}", { label: loadingLabel.replace(/^正在/, "") })} cancel={onCancel} />
      ) : null}
      {!isFetching && isCancelled ? (
        <QueryRefreshCancelledState retry={onRetry} dismiss={onDismissCancellation} />
      ) : null}
      {!isFetching && !isCancelled && error ? (
        <QueryPartialDataState message={errorMessage(error, fallbackError)} retry={onRetry} />
      ) : null}
      {children}
    </>
  );
}

const defaultStatusLabels: Record<string, MessageKey> = {
  acknowledged: "已确认",
  active: "正常",
  approved: "已批准",
  available: "可查看",
  blocked: "未启用或受阻",
  conflict: "存在冲突",
  degraded: "存在异常",
  disabled: "未启用",
  done: "已完成",
  draft: "待治理",
  empty: "暂无数据",
  expired: "已过期",
  external: "需外部探测",
  failed: "失败",
  fresh: "新鲜",
  healthy: "正常",
  high: "高",
  low: "低",
  medium: "中",
  not_observed: "暂无记录",
  "not observed": "暂无记录",
  open: "待处置",
  opened: "已开启",
  partial: "部分完成",
  pending: "待处理",
  passed: "通过",
  published: "已发布",
  ready: "就绪",
  rejected: "已排除",
  ready_to_resolve: "待关闭",
  "ready to resolve": "待关闭",
  recovered: "已恢复",
  regressed: "已回归",
  review_pending: "待审核",
  running: "处理中",
  stale: "需更新",
  succeeded: "已完成",
  superseded: "历史版本",
  unavailable: "暂不可用",
  verified: "已查证",
  valid: "有效",
  waived: "已豁免",
  resolved: "已解决",
};

export function statusLabel(value: string): string {
  const normalized = value.toLowerCase();
  const message = defaultStatusLabels[normalized];
  return message ? t(message) : value.replaceAll("_", " ");
}

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  useLocale();
  const normalized = value.toLowerCase();
  const tone = [
    "active",
    "done",
    "succeeded",
    "published",
    "approved",
    "verified",
    "passed",
    "fresh",
    "healthy",
    "recovered",
    "valid",
    "resolved",
  ].includes(normalized)
    ? "success"
    : ["failed", "unavailable", "rejected", "conflict", "high", "stale", "regressed"].includes(normalized)
      ? "danger"
      : ["running", "review_pending", "pending", "proposed", "medium", "open", "acknowledged"].includes(normalized)
        ? "warning"
        : "neutral";
  return <span className={`badge badge-${tone}`}>{label ?? statusLabel(value)}</span>;
}

export function SectionHeader({ title, detail, actions }: { title: string; detail?: string; actions?: ReactNode }) {
  useLocale();
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {detail ? <p>{detail}</p> : null}
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function formatDate(value: string | null | undefined, includeTime = false): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat(formattingLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function compactNumber(value: number): string {
  const threshold = getLocale() === "en" ? 1_000 : 10_000;
  return new Intl.NumberFormat(formattingLocale(), {
    notation: Math.abs(value) >= threshold ? "compact" : "standard",
  }).format(value);
}

export function humanBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

export function stringifyParty(value: Record<string, unknown>): string {
  const preferred = value.name ?? value.organization ?? value.party;
  return typeof preferred === "string" ? preferred : JSON.stringify(value);
}
