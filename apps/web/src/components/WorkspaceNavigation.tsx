import {
  Building2,
  CreditCard,
  Database,
  FileBadge2,
  FlaskConical,
  ListChecks,
  Newspaper,
  Search,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { type MessageKey, t, useLocale } from "../lib/i18n";
import type { UserRole } from "../lib/types";
import { researchWorkflowForView, researchWorkflows } from "../lib/workspace/researchNavigation";
import { canAccessView, type ViewKey, type WorkbenchKey } from "../lib/workspaceRouting";

type Item = { key: ViewKey; label: MessageKey; icon: typeof Search };
const researchIcons: Partial<Record<ViewKey, typeof Search>> = {
  explorer: Search,
  pipeline: FlaskConical,
  patents: FileBadge2,
  news: Newspaper,
  collections: ListChecks,
};
const internal: Item[] = [
  { key: "factory", label: "数据工厂", icon: Database },
  { key: "governance", label: "AI 审核", icon: ShieldCheck },
  { key: "commercial", label: "商业运营", icon: CreditCard },
  { key: "enterprise", label: "企业管理", icon: Building2 },
  { key: "environment", label: "环境管理", icon: Settings2 },
];

export function WorkspaceNavigation({
  workbench,
  role,
  activeView,
  sourceView,
  collapsed,
  onView,
}: {
  workbench: WorkbenchKey;
  role: UserRole;
  activeView: ViewKey;
  sourceView?: ViewKey | null;
  collapsed: boolean;
  onView: (view: ViewKey) => void;
}) {
  useLocale();
  const activeWorkflow = researchWorkflowForView(activeView, sourceView);
  const items: Item[] =
    workbench === "research"
      ? researchWorkflows.map((workflow) => ({
          key: workflow.destinations[0].view,
          label: workflow.label,
          icon: researchIcons[workflow.destinations[0].view] ?? Search,
        }))
      : internal;
  function buttons() {
    return items
      .filter((item) => canAccessView(item.key, role))
      .map(({ key, label, icon: Icon }) => {
        const active = workbench === "research" ? activeWorkflow?.label === label : activeView === key;
        return (
          <button
            key={key}
            className={`nav-button ${active ? "active" : ""}`}
            type="button"
            onClick={() => onView(key)}
            aria-current={active ? "page" : undefined}
            title={collapsed ? t(label) : undefined}
          >
            <Icon size={18} aria-hidden="true" />
            <span>{t(label)}</span>
          </button>
        );
      });
  }
  return (
    <div className="sidebar-navigation-sections">
      <nav className="sidebar-primary-nav" aria-label={t("主导航")}>
        {buttons()}
      </nav>
    </div>
  );
}
