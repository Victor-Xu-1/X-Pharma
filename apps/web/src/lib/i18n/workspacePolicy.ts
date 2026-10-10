import { createTranslator } from "./translator";
export const workspacePolicyMessages = {
  工作台导出策略: "Workspace export policy",
  控制外部用户工作台可导出的格式字段单次上限和授权标注:
    "Manage formats, fields, record limits and attribution for the research workbench.",
  尚未配置导出策略: "No export policy configured",
  "当前版本 {version}": "Current policy version {version}",
  策略变更必须使用新版本号历史导出事件保持不可修改:
    "Use a new version for policy changes. Historical export records remain immutable.",
  启用外部工作台人工导出: "Enable human exports from the research workbench",
  允许格式: "Allowed formats",
  允许字段: "Allowed fields",
  通用字段: "General fields",
  序号: "Position",
  "稳定 ID": "Stable ID",
  实体类型: "Entity type",
  名称: "Name",
  描述: "Description",
  外部标识: "External identifiers",
  审核状态: "Review status",
  创建时间: "Created at",
  更新时间: "Updated at",
  策略版本: "Policy version",
  单次导出上限: "Maximum records per export",
  授权标注: "Attribution",
  保存中: "Saving",
  保存导出策略: "Save export policy",
  正在加载工作台导出策略: "Loading workspace export policy",
  工作台导出策略加载失败: "Could not load workspace export policy",
  导出策略保存失败: "Could not save export policy",
  "导出策略 {version} 已生效": "Export policy {version} is active",
  "保存返回的策略与原版本不匹配；请重新读取后核对。":
    "The returned policy does not match the submitted version. Reload and review the authoritative policy.",
} as const;
export const workspacePolicyText = createTranslator(workspacePolicyMessages);
