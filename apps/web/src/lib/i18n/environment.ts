import type { EnvironmentProbeRead } from "../generated";
import { createTranslator } from "./translator";

export const environmentMessages = {
  环境检测: "Environment checks",
  安装与修复: "Installation and repair",
  运行与发布证据: "Runtime and release evidence",
  环境管理功能: "Environment management functions",
  正在检测网关与主机环境: "Checking gateway and host environment",
  "状态读取 {time}": "Status read at {time}",
  刷新状态: "Refresh status",
  依赖就绪概览: "Dependency readiness overview",
  依赖可用: "Dependencies available",
  需修复或更新: "Repair or update required",
  待核对: "Unverified",
  应用网关: "Application gateway",
  项目环境: "Project environment",
  "{count} 项需处理：{labels}": "{count} items need attention: {labels}",
  "仅汇总网关与所报项目依赖，不代表完整离线包或生产环境已验收。数据库、采集、身份及恢复需独立验证。未声明明确版本要求时，不判定为兼容。":
    "This summarizes only gateway and reported project dependencies, not acceptance of a complete offline package or production environment. Database, ingestion, identity and recovery require separate verification. Compatibility is not inferred without a declared version requirement.",
  "主机检测 {time} · 源码 {revision} · {state} · 可用空间 {space} GiB":
    "Host checked at {time} · Source {revision} · {state} · Free space {space} GiB",
  源码干净: "Clean source",
  存在未提交变更: "Uncommitted changes present",
  查看网关依赖明细: "View gateway dependency details",
  "网关进程的实际版本，不代表主机或其他容器已经健康。":
    "Actual gateway process versions do not establish the health of the host or other containers.",
  网关依赖版本: "Gateway dependency versions",
  查看主机与项目依赖明细: "View host and project dependency details",
  主机依赖版本: "Host dependency versions",
  "最近安装：{recipe} · {status} · {detail} · {revision}":
    "Latest installation: {recipe} · {status} · {detail} · {revision}",
  成功: "Succeeded",
  执行中: "Running",
  失败: "Failed",
  "安装时源码 {revision}": "Source at installation {revision}",
  "旧记录未绑定源码，不能作为当前源码的安装证明":
    "This legacy record is not source-bound and cannot establish installation of the current source",
  "尚无有效的主机报告。可在“安装与修复”查看接入步骤。":
    "No valid host report is available. See Installation and repair for connection steps.",
  "{label}（可滚动）": "{label} (scrollable)",
  组件: "Component",
  实测值: "Observed value",
  项目要求: "Project requirement",
  状态: "Status",
  未检测到: "Not detected",
  未声明: "Not declared",
  符合已声明要求: "Meets declared requirements",
  已检测: "Detected",
  未安装: "Not installed",
  版本不符: "Version mismatch",
  检查失败: "Check failed",
  尚未验证: "Not verified",
  暂无探针记录: "No probe observations",
  "报告未提供依赖探针，尚不能验证可用性或兼容性。":
    "The report provides no dependency probes; availability and compatibility have not been verified.",
} as const;

export const environmentProbeStateKeys = {
  present: "已检测",
  missing: "未安装",
  mismatch: "版本不符",
  blocked: "检查失败",
  unverified: "尚未验证",
} as const satisfies Record<EnvironmentProbeRead["status"], keyof typeof environmentMessages>;

/** Exact first-party environment boilerplate only; unknown diagnostic text remains literal. */
export const environmentSourceMessages = {
  "尚未连接主机检测报告；网关内的运行版本不等同于主机安装状态。":
    "No host report is connected; gateway runtime versions do not establish host installation state.",
  "主机报告已超过 24 小时；请重新检测后生成安装计划。":
    "The host report is over 24 hours old; inspect the host again before preparing a plan.",
  "主机报告不属于当前产品版本；请重新检测。":
    "The host report does not match the current product version; inspect the host again.",
  "主机侧真实检测报告；安装执行必须在该主机受控完成。":
    "This is an actual host inspection report; installation must be explicitly performed on that host.",
  "主机报告尚不存在；不会把缺失的探针当作健康。":
    "The host report does not exist; missing probes are not treated as healthy.",
  "主机报告无效或不可安全读取；请重新生成，原始错误和路径不对外披露。":
    "The host report is invalid or cannot be read safely; regenerate it. Original errors and paths are not disclosed.",
  人员身份与账号恢复: "Human identity and account recovery",
  "本地账号（邮箱未验证）": "Local account (email ownership not verified)",
  "企业 OIDC 配置": "Enterprise OIDC configuration",
  "正式环境使用企业 OIDC 与受控恢复策略": "Production requires enterprise OIDC and controlled recovery",
  "本地登录不能作为正式身份验收；企业 IdP、账号恢复和目标部署必须提供独立实测证据。":
    "Local login does not establish production identity acceptance; enterprise IdP, account recovery and target deployment require independent runtime evidence.",
  "Python 依赖": "Python dependencies",
  前端依赖: "Frontend dependencies",
  部署工具: "Deployment tools",
  "按 uv.lock 安装到当前项目的 .venv，不修改系统 Python。":
    "Install from uv.lock into this project's .venv without modifying system Python.",
  "使用项目声明的 pnpm 和冻结锁文件，不升级依赖。":
    "Use the declared pnpm version and frozen lockfile without upgrading dependencies.",
  "通过项目唯一安装器校验并安装固定摘要的 kubectl。":
    "Use the project's sole installer to verify and install checksum-pinned kubectl.",
  "当前网关环境未发现该发行包。": "This distribution was not found in the gateway environment.",
  "当前网关进程实际使用的解释器。": "Interpreter actually used by the gateway process.",
  "已安装的发行包版本；不替代服务健康检查。":
    "Installed distribution version; this does not replace service health checks.",
  操作系统: "Operating system",
  "项目 Python": "Project Python",
  "系统 Python（工具探针）": "System Python (tool probe)",
  "pnpm（项目缓存版本）": "pnpm (project cache version)",
  "项目 .venv 解释器": "Project .venv interpreter",
  "Python 锁定依赖": "Locked Python dependencies",
  前端项目依赖: "Frontend project dependencies",
  "读取当前项目 .venv 的解释器，不用系统 python3 代替。":
    "Read this project's .venv interpreter, not the system python3.",
  "检测实际主机，不使用网关容器版本代替。": "Inspect the actual host, not the gateway container version.",
  "只读版本检查；缺失或超时不会触发自动下载安装。":
    "Read-only version checks; missing data or timeouts do not trigger automatic downloads or installation.",
  "请先生成当前版本的有效主机检测报告。": "First produce a valid host report for the current version.",
  "主机报告缺少项目声明的包管理器；请重新检测。":
    "The host report lacks the declared package manager; inspect the host again.",
} as const;
const sourceText = createTranslator(environmentSourceMessages);
export function environmentSourceText(value: string): string {
  return Object.hasOwn(environmentSourceMessages, value)
    ? sourceText(value as keyof typeof environmentSourceMessages)
    : value;
}
