import {
  Activity,
  Atom,
  Bell,
  BookOpen,
  Building2,
  ClipboardList,
  CreditCard,
  Database,
  FileBadge2,
  FileSearch,
  FlaskConical,
  Handshake,
  Landmark,
  ListChecks,
  Newspaper,
  Search,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import type { UserRole } from "../lib/types";
import { canAccessView, type ViewKey, type WorkbenchKey } from "../lib/workspaceRouting";

type Item = { key: ViewKey; label: string; icon: typeof Search };
const research: Item[] = [
  { key: "explorer", label: "情报检索", icon: Search },
  { key: "pipeline", label: "药物与管线", icon: FlaskConical },
  { key: "trials", label: "临床试验", icon: ClipboardList },
  { key: "patents", label: "专利情报", icon: FileBadge2 },
  { key: "deals", label: "交易与公司", icon: Handshake },
  { key: "regulatory", label: "监管与安全", icon: Landmark },
  { key: "epidemiology", label: "流行病学", icon: Activity },
  { key: "news", label: "新闻与会议", icon: Newspaper },
  { key: "chemistry", label: "结构检索", icon: Atom },
];
const personalResearch: Item[] = [
  { key: "collections", label: "对比列表", icon: ListChecks },
  { key: "monitoring", label: "监控与提醒", icon: Bell },
  { key: "knowledge", label: "知识专题", icon: BookOpen },
  { key: "evidence", label: "证据查证", icon: FileSearch },
];
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
  collapsed,
  onView,
}: {
  workbench: WorkbenchKey;
  role: UserRole;
  activeView: ViewKey;
  collapsed: boolean;
  onView: (view: ViewKey) => void;
}) {
  function buttons(items: Item[]) {
    return items
      .filter((item) => canAccessView(item.key, role))
      .map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          className={`nav-button ${activeView === key ? "active" : ""}`}
          type="button"
          onClick={() => onView(key)}
          aria-current={activeView === key ? "page" : undefined}
          title={collapsed ? label : undefined}
        >
          <Icon size={18} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ));
  }
  return (
    <div className="sidebar-navigation-sections">
      <nav className="sidebar-primary-nav" aria-label="主导航">
        {buttons(workbench === "research" ? research : internal)}
      </nav>
      {workbench === "research" ? (
        <nav className="sidebar-primary-nav sidebar-research-nav" aria-label="我的研究">
          {!collapsed ? <p className="sidebar-group-label">我的研究</p> : null}
          {buttons(personalResearch)}
        </nav>
      ) : null}
    </div>
  );
}
