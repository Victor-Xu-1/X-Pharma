import { useLocale } from "../lib/i18n";
import { accountInvitationText as t } from "../lib/i18n/accountInvitations";
import { InvitationSecret } from "./accountInvitations/InvitationSecret";
import type { AccountInvitationWorkspace } from "./accountInvitations/useAccountInvitations";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "./common";
import { FormStatus } from "./FormStatus";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

const invitationLabels = { active: "有效", consumed: "已使用", revoked: "已撤销", expired: "已过期" } as const;
export function AccountInvitationPanel({ workspace }: { workspace: AccountInvitationWorkspace }) {
  useLocale();
  const {
    authMode,
    invitations,
    email,
    setEmail,
    validHours,
    setValidHours,
    issued,
    closeSecret,
    pending,
    issuing,
    actionError,
    readReady,
    submit,
    revoke,
  } = workspace;
  if (authMode !== "local")
    return <p role="status">{t("当前使用企业身份系统，请在组织身份系统创建账号并绑定已有企业身份。")}</p>;
  return (
    <section className="enterprise-access" aria-label={t("注册邀请码管理")}>
      <header>
        <h2>{t("内部账号注册邀请")}</h2>
        <p>
          {t(
            "只有管理员可以发放邀请码。新账号以内部分析员身份加入当前企业，不自动获得管理员权限；已有邮箱账号不自动迁移企业。",
          )}
        </p>
      </header>
      <form className="account-invitation-form" onSubmit={(event) => void submit(event)} aria-busy={pending}>
        <label>
          <span>{t("受邀邮箱")}</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            maxLength={320}
            required
            autoComplete="off"
            disabled={pending}
          />
        </label>
        <label>
          <span>{t("有效小时")}</span>
          <input
            type="number"
            value={validHours}
            onChange={(event) => setValidHours(Number(event.target.value))}
            min={1}
            max={168}
            required
            disabled={pending}
          />
        </label>
        <button
          className="primary-button"
          type="submit"
          disabled={
            pending ||
            !readReady ||
            !email.trim() ||
            !Number.isInteger(validHours) ||
            validHours < 1 ||
            validHours > 168
          }
        >
          {t(issuing ? "生成中…" : "生成注册邀请码")}
        </button>
      </form>
      <FormStatus pending={pending} error={actionError} pendingLabel={t("正在提交邀请操作…")} />
      {invitations.isPending ? (
        <Spinner label={t("正在读取注册邀请")} />
      ) : invitations.error ? (
        <ErrorState message={t("注册邀请读取失败")} retry={() => void invitations.refetch()} />
      ) : invitations.data?.length ? (
        <ScrollableTableRegion className="enterprise-table" ariaLabel={t("注册邀请记录滚动区域")}>
          <table aria-label={t("注册邀请记录")}>
            <thead>
              <tr>
                <th>{t("邮箱")}</th>
                <th>{t("状态")}</th>
                <th>{t("有效期")}</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {invitations.data.map((item) => (
                <tr key={item.id}>
                  <td>{item.email}</td>
                  <td>
                    <StatusBadge value={item.status} label={t(invitationLabels[item.status])} />
                  </td>
                  <td>{formatDate(item.expires_at, true)}</td>
                  <td>
                    <button
                      className="text-button"
                      type="button"
                      disabled={pending || !readReady || item.status !== "active"}
                      onClick={() => void revoke(item.id)}
                    >
                      {t("撤销邀请")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <EmptyState
          title={t("暂无注册邀请")}
          detail={t("生成邀请码后，受邀用户可在内部工作台的注册入口设置自己的密码。")}
        />
      )}
      {issued ? <InvitationSecret issued={issued} close={closeSecret} /> : null}
    </section>
  );
}
