import { CircleUserRound, LogOut } from "lucide-react";
import type { ReactNode } from "react";
import { t, useLocale } from "../lib/i18n";

import type { User } from "../lib/types";
import type { ViewKey } from "../lib/workspaceRouting";
import { OrganizationPanel } from "./OrganizationPanel";

export function WorkspaceAccountNavigation({
  user,
  researchWorkbench,
  navigationView,
  collapsed,
  collapseControl,
  onView,
  onLogout,
  logoutPending,
  logoutError,
}: {
  user: User;
  researchWorkbench: boolean;
  navigationView: ViewKey;
  collapsed: boolean;
  collapseControl: ReactNode;
  onView: (view: ViewKey) => void;
  onLogout: () => void;
  logoutPending: boolean;
  logoutError: string | null;
}) {
  useLocale();
  return (
    <nav className="sidebar-account-nav" aria-label={t("账户导航")}>
      <div className="sidebar-account-row">
        {researchWorkbench ? (
          <button
            className={`nav-button sidebar-account-button ${navigationView === "overview" ? "active" : ""}`}
            type="button"
            onClick={() => onView("overview")}
            aria-current={navigationView === "overview" ? "page" : undefined}
            aria-label={t("用户中心")}
            title={collapsed ? t("用户中心") : undefined}
          >
            <CircleUserRound size={19} />
            <span className="sidebar-account-copy">
              <strong>{t("用户中心")}</strong>
              <small>{user.display_name}</small>
            </span>
          </button>
        ) : (
          <div className="nav-button sidebar-account-button" title={collapsed ? user.display_name : undefined}>
            <CircleUserRound size={19} aria-hidden="true" />
            <span className="sidebar-account-copy">
              <strong>{user.display_name}</strong>
              <small>{t("内部工作台")}</small>
            </span>
          </div>
        )}
        {collapseControl}
      </div>
      <OrganizationPanel />
      <button
        className="nav-button"
        type="button"
        onClick={onLogout}
        disabled={logoutPending}
        title={t("退出账号")}
        aria-label={t("退出账号")}
      >
        <LogOut size={18} />
        <span>{logoutPending ? t("退出中…") : t("退出账号")}</span>
      </button>
      {logoutError ? (
        <p className="form-error" role="alert">
          {logoutError}
        </p>
      ) : null}
    </nav>
  );
}
