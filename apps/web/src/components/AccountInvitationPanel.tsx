import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, X } from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiError } from "../lib/api";
import { accountInvitations, issueAccountInvitation, revokeAccountInvitation } from "../lib/contracts/accounts";
import type { AuthMode } from "../lib/contracts/session";
import type { InvitationCreate, InvitationIssued } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { type AccountInvitationMessageKey, accountInvitationText as t } from "../lib/i18n/accountInvitations";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "./common";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

const key = ["enterprise", "account-invitations"] as const;
const invitationLabels = { active: "有效", consumed: "已使用", revoked: "已撤销", expired: "已过期" } as const;

function failureMessage(error: unknown) {
  return error instanceof ApiError && [403, 409].includes(error.status) ? error.message : t("邀请操作失败，请稍后重试");
}

function InvitationSecret({ issued, close }: { issued: InvitationIssued; close: () => void }) {
  useLocale();
  const ref = useModalFocus<HTMLElement>(true, close);
  const [copyStatus, setCopyStatus] = useState<AccountInvitationMessageKey | null>(null);
  async function copy() {
    try {
      await navigator.clipboard.writeText(issued.code);
      setCopyStatus("邀请码已复制");
    } catch {
      setCopyStatus("无法写入剪贴板，请选中邀请码手动复制");
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={t("新生成的注册邀请码")}
        tabIndex={-1}
        ref={ref}
      >
        <header>
          <h3>{t("注册邀请码")}</h3>
          <button className="icon-button" type="button" onClick={close} aria-label={t("关闭邀请码")}>
            <X size={18} />
          </button>
        </header>
        <div className="account-invitation-content">
          <p>
            {t("绑定邮箱：")}
            {issued.invitation.email}
          </p>
          <p>
            {t("有效期至：")}
            {formatDate(issued.invitation.expires_at, true)}
          </p>
          <label>
            <span>{t("一次性邀请码")}</span>
            <input
              value={issued.code}
              readOnly
              onFocus={(event) => event.currentTarget.select()}
              data-modal-autofocus="true"
            />
          </label>
          <p className="form-footnote">{t("邀请码仅显示这一次。请私下交给绑定邮箱的用户；注册后立即失效。")}</p>
          <button className="secondary-button" type="button" onClick={() => void copy()}>
            <Copy size={16} />
            {t("复制邀请码")}
          </button>
          {copyStatus ? <p role="status">{t(copyStatus)}</p> : null}
          <button className="primary-button" type="button" onClick={close}>
            {t("完成")}
          </button>
        </div>
      </section>
    </div>
  );
}

export function AccountInvitationPanel({ authMode }: { authMode: AuthMode }) {
  useLocale();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [validHours, setValidHours] = useState(24);
  const [issued, setIssued] = useState<InvitationIssued | null>(null);
  const invitations = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => accountInvitations(signal),
    enabled: authMode === "local",
  });
  const create = useMutation({
    mutationFn: async (payload: InvitationCreate) => {
      const receipt = await issueAccountInvitation(payload);
      // Keep the one-time secret only in the visible modal, never in Query's mutation history.
      setIssued(receipt);
      return receipt.invitation;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const revoke = useMutation({
    mutationFn: revokeAccountInvitation,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    revoke.reset();
    create.mutate({ email: email.trim(), valid_hours: validHours });
  }
  function closeSecret() {
    setIssued(null);
    create.reset();
  }
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
      <form className="account-invitation-form" onSubmit={submit}>
        <label>
          <span>{t("受邀邮箱")}</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            maxLength={320}
            required
            autoComplete="off"
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
          />
        </label>
        <button
          className="primary-button"
          type="submit"
          disabled={
            create.isPending || !email.trim() || !Number.isInteger(validHours) || validHours < 1 || validHours > 168
          }
        >
          {t(create.isPending ? "生成中…" : "生成注册邀请码")}
        </button>
      </form>
      {create.error || revoke.error ? (
        <p className="form-error" role="alert">
          {failureMessage(create.error ?? revoke.error)}
        </p>
      ) : null}
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
                      disabled={revoke.isPending || item.status !== "active"}
                      onClick={() => {
                        create.reset();
                        revoke.mutate(item.id);
                      }}
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
