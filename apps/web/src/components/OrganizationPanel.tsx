import { Building2 } from "lucide-react";
import { createPortal } from "react-dom";
import { t, uiFeedback, useLocale } from "../lib/i18n";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, Spinner } from "./common";
import { FormStatus } from "./FormStatus";
import { useOrganizationMembership } from "./identity/useOrganizationMembership";
import { type OrganizationControls, useOrganizationControls } from "./OrganizationContext";
import "./OrganizationPanel.css";

export function OrganizationPanel() {
  useLocale();
  const controls = useOrganizationControls();
  return controls ? <MembershipPanel controls={controls} /> : null;
}

function MembershipPanel({ controls }: { controls: OrganizationControls }) {
  useLocale();
  const state = useOrganizationMembership(controls);
  const busy = Boolean(state.operation.pending);
  const focus = useModalFocus<HTMLDivElement>(state.open, state.close, { closeOnEscape: !busy });
  return (
    <>
      <button
        type="button"
        className="nav-button"
        onClick={state.openPanel}
        aria-label={t("组织与账号")}
        title={t("组织与账号")}
      >
        <Building2 size={18} aria-hidden="true" />
        <span className="sidebar-account-copy">
          <strong className="sidebar-nav-label">{t("组织与账号")}</strong>
          {controls.organizationName ? (
            <small title={controls.organizationName}>{controls.organizationName}</small>
          ) : null}
        </span>
      </button>
      {state.open
        ? createPortal(
            <div className="modal-backdrop">
              <div
                ref={focus}
                className="modal-panel organization-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="organization-title"
                aria-busy={busy}
                tabIndex={-1}
              >
                <header className="modal-header">
                  <h2 id="organization-title">{t("组织与账号")}</h2>
                  <button type="button" className="secondary-button" disabled={busy} onClick={state.close}>
                    {t("关闭")}
                  </button>
                </header>
                <p>{t("每次会话只访问一个组织。切换不会合并或转移研究、数据、授权与历史记录。")}</p>
                {state.organizations.isPending ? (
                  <Spinner label={t("正在读取组织成员资格")} />
                ) : state.organizations.error ? (
                  <ErrorState message={t("组织成员资格读取失败")} retry={() => void state.organizations.refetch()} />
                ) : state.organizations.data?.length ? (
                  <ul className="permission-list">
                    {state.organizations.data.map((organization) => (
                      <li key={organization.tenant_id}>
                        <strong>{organization.name}</strong>
                        <span>
                          {organization.role} ·{" "}
                          {organization.selected ? t("当前组织") : organization.active ? t("可切换") : t("已停用")}
                        </span>
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={!state.readReady || !organization.active || organization.selected || busy}
                          onClick={() => void state.selectOrganization(organization.tenant_id)}
                        >
                          {t("切换到 {organization}", { organization: organization.name })}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState title={t("没有组织成员资格")} detail={t("请联系组织管理员获取邀请码。")} />
                )}
                <form className="modal-form" onSubmit={state.submit}>
                  <h3>{t("接受组织邀请")}</h3>
                  <fieldset
                    className="organization-form-fields"
                    aria-label={t("接受组织邀请")}
                    disabled={busy || !state.readReady}
                  >
                    <label>
                      <span>{t("管理员邀请码")}</span>
                      <input
                        type="password"
                        value={state.code}
                        onChange={(event) => state.setCode(event.target.value)}
                        autoComplete="off"
                        spellCheck={false}
                        maxLength={2048}
                        required
                      />
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={state.confirmed}
                        onChange={(event) => state.setConfirmed(event.target.checked)}
                        required
                      />
                      <span>{t("我确认加入邀请的组织，原组织的数据不会共享。")}</span>
                    </label>
                  </fieldset>
                  <FormStatus
                    pending={busy}
                    pendingLabel={state.operation.pending === "join" ? t("接受中…") : t("正在确认组织会话")}
                    error={state.feedback?.kind === "error" ? uiFeedback(state.feedback.text) : undefined}
                  />
                  {state.feedback?.kind === "success" ? <p role="status">{uiFeedback(state.feedback.text)}</p> : null}
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={!state.readReady || !state.code.trim() || !state.confirmed || busy}
                  >
                    {t("确认加入组织")}
                  </button>
                </form>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
