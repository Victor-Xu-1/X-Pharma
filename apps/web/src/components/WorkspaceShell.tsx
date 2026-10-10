import { ChevronLeft, ChevronRight, Menu, X } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { type MessageKey, t, useLocale } from "../lib/i18n";

import { OPERATIONS_NAME, PRODUCT_NAME, PRODUCT_RELEASE } from "../lib/product";
import type { User } from "../lib/types";
import { useCompactNavigation } from "../lib/useCompactNavigation";
import { useModalFocus } from "../lib/useModalFocus";
import type { ViewKey, WorkbenchKey } from "../lib/workspaceRouting";
import { BrandMark } from "./BrandMark";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ResearchViewNavigation } from "./ResearchViewNavigation";
import { WorkspaceAccountNavigation } from "./WorkspaceAccountNavigation";
import { WorkspaceNavigation } from "./WorkspaceNavigation";

const titles: Record<ViewKey, MessageKey> = {
  overview: "用户中心",
  explorer: "全局情报检索",
  chemistry: "化学结构检索",
  pipeline: "药物与研发管线",
  trials: "临床试验与结果",
  patents: "专利族与资产关联",
  deals: "交易与资产",
  regulatory: "监管事件与安全时间线",
  epidemiology: "流行病学与疾病负担",
  news: "新闻、公告与会议动态",
  target: "靶点全景档案",
  drug: "药物专业档案",
  company: "公司专业档案",
  disease: "疾病与登记条件",
  entity: "多领域情报档案",
  evidence: "原始资料查证",
  knowledge: "版本化知识专题",
  monitoring: "情报监控与变更提醒",
  collections: "对比列表",
  factory: "自动数据工厂",
  governance: "AI 信息审核",
  commercial: "商业运营",
  enterprise: "企业账户与审计",
  environment: "运行环境与安装管理",
};

export function WorkspaceShell({
  user,
  activeWorkbench,
  activeView,
  pendingView = null,
  sourceView = null,
  researchDetail = false,
  onView,
  onLogout,
  logoutPending = false,
  logoutError = null,
  children,
}: {
  user: User;
  activeWorkbench: WorkbenchKey;
  activeView: ViewKey;
  pendingView?: ViewKey | null;
  sourceView?: ViewKey | null;
  researchDetail?: boolean;
  onView: (view: ViewKey) => void;
  onLogout: () => void;
  logoutPending?: boolean;
  logoutError?: string | null;
  children: ReactNode;
}) {
  useLocale();
  const [collapsed, setCollapsed] = useState(false);
  const compact = useCompactNavigation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navigationClosing, setNavigationClosing] = useState(false);
  const sidebarScrimRef = useRef<HTMLButtonElement>(null);
  const mobileNavigationRef = useModalFocus<HTMLElement>(mobileOpen, () => setMobileOpen(false), {
    restoreFocus: !navigationClosing,
    backgroundExceptions: [sidebarScrimRef],
  });
  const pageHeadingRef = useRef<HTMLHeadingElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const previousView = useRef(activeView);
  const heading = t(titles[activeView]);
  const navigationView = pendingView ?? activeView;
  const researchWorkbench = activeWorkbench === "research";
  const recordPage = researchDetail || ["target", "drug", "company", "disease", "entity"].includes(activeView);
  useEffect(() => {
    if (!compact) setMobileOpen(false);
  }, [compact]);
  useEffect(() => {
    if (previousView.current === activeView) return;
    previousView.current = activeView;
    pageHeadingRef.current?.focus({ preventScroll: true });
  }, [activeView]);

  function navigate(view: ViewKey) {
    setNavigationClosing(true);
    onView(view);
    setMobileOpen(false);
  }

  const collapseControl = (
    <button
      className="collapse-button"
      type="button"
      onClick={() => setCollapsed((value) => !value)}
      title={collapsed ? t("展开导航") : t("收起导航")}
      aria-label={collapsed ? t("展开导航") : t("收起导航")}
    >
      {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
    </button>
  );

  return (
    <div
      className={`workspace-shell ${researchWorkbench ? "research-workbench" : "internal-workbench"} ${
        collapsed ? "sidebar-collapsed" : ""
      }`}
    >
      <button
        className="skip-link"
        type="button"
        onClick={() => {
          mainRef.current?.focus();
        }}
      >
        {t("跳到主要内容")}
      </button>
      <aside
        id="workspace-navigation"
        ref={mobileNavigationRef}
        className={`workspace-sidebar ${mobileOpen ? "mobile-open" : ""}`}
        aria-label={t("工作台导航")}
        inert={compact && !mobileOpen}
        aria-hidden={compact && !mobileOpen ? true : undefined}
        tabIndex={mobileOpen ? -1 : undefined}
      >
        <div className="sidebar-head">
          <div className="brand-lockup" title={researchWorkbench ? PRODUCT_NAME : OPERATIONS_NAME}>
            <BrandMark />
            <span className="brand-copy">
              <strong>{PRODUCT_NAME}</strong>
              <small>
                <span>{researchWorkbench ? t("医药研发情报") : t("内部管理工作台")}</span> ·{" "}
                <span>{PRODUCT_RELEASE}</span>
              </small>
            </span>
          </div>
          <button
            className="icon-button mobile-only"
            type="button"
            onClick={() => setMobileOpen(false)}
            title={t("关闭导航")}
            aria-label={t("关闭导航")}
          >
            <X size={19} />
          </button>
        </div>
        <WorkspaceNavigation
          workbench={activeWorkbench}
          role={user.role}
          activeView={navigationView}
          sourceView={sourceView}
          collapsed={collapsed}
          onView={navigate}
        />
        <WorkspaceAccountNavigation
          user={user}
          researchWorkbench={researchWorkbench}
          navigationView={navigationView}
          collapsed={collapsed}
          collapseControl={collapseControl}
          onView={navigate}
          onLogout={onLogout}
          logoutPending={logoutPending}
          logoutError={logoutError}
        />
      </aside>
      {mobileOpen ? (
        <button
          ref={sidebarScrimRef}
          type="button"
          className="sidebar-scrim"
          aria-label={t("关闭导航")}
          onClick={() => setMobileOpen(false)}
        />
      ) : null}
      <div className="workspace-main">
        <header className={`topbar ${researchWorkbench ? "public-topbar" : ""}`}>
          <button
            className="icon-button mobile-only"
            type="button"
            onClick={() => {
              setNavigationClosing(false);
              setMobileOpen(true);
            }}
            title={t("打开导航")}
            aria-label={t("打开导航")}
            aria-expanded={mobileOpen}
            aria-controls="workspace-navigation"
          >
            <Menu size={20} />
          </button>
          <span className="mobile-workspace-context" aria-hidden="true">
            {researchWorkbench ? t("X-Pharma · 研究工作台") : t("X-Pharma · 内部管理")}
          </span>
        </header>
        <main
          ref={mainRef}
          id="workspace-main"
          tabIndex={-1}
          className="workspace-content"
          aria-labelledby="workspace-page-title"
          aria-busy={pendingView ? "true" : undefined}
        >
          <div className={`page-heading${recordPage ? " record-page-heading" : ""}`}>
            <h1 id="workspace-page-title" ref={pageHeadingRef} tabIndex={-1} style={{ outline: "none" }}>
              {heading}
            </h1>
            <LanguageSwitcher />
          </div>
          {researchWorkbench && !researchDetail ? (
            <ResearchViewNavigation activeView={navigationView} onView={navigate} />
          ) : null}
          {children}
        </main>
      </div>
    </div>
  );
}
