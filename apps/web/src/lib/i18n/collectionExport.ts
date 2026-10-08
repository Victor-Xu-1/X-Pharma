import { createTranslator } from "./translator";

export const collectionExportMessages = {
  导出列表: "Export list",
  列表导出: "List export",
  "最多 {count} 个对象": "Up to {count} objects",
  正在读取导出策略: "Loading export policy",
  导出策略读取失败: "Could not read the export policy",
  重新读取导出策略: "Reload export policy",
  格式: "Format",
  导出格式: "Export format",
  导出字段: "Export fields",
  "使用说明：{attribution}": "Usage requirements: {attribution}",
  正在生成列表导出文件: "Generating the list export",
  生成中: "Generating",
  导出: "Export",
  序号: "Position",
  记录编号: "Record ID",
  类型: "Type",
  名称: "Name",
  描述: "Description",
  外部标识: "External identifiers",
  创建时间: "Created",
  更新时间: "Updated",
  "本组织尚未配置导出策略；请联系管理员。": "Your organization has no export policy. Contact an administrator.",
  "本组织尚未开放列表导出；请联系管理员。": "Your organization has not enabled list exports. Contact an administrator.",
  "导出策略缺少必需字段（记录编号、类型、名称）；请联系管理员核对。":
    "The export policy is missing required fields (Record ID, Type, Name). Ask an administrator to review it.",
  "导出策略的记录上限无效；请联系管理员核对。":
    "The export policy has an invalid record limit. Ask an administrator to review it.",
  "当前列表尚无可导出对象；先加入关注对象，再导出。": "This list has no objects to export. Add objects first.",
  "列表含 {count} 个对象，超过授权上限 {limit} 个；请先精简列表。":
    "This list contains {count} objects, exceeding the licensed limit of {limit}. Reduce the list first.",
  "当前列表刷新失败；请先恢复连接并核对当前版本。":
    "The list could not be refreshed. Reconnect and verify the current version first.",
  "正在核对当前列表版本，完成后可导出。": "Verifying the current list version. Export will be available afterwards.",
  "列表正在更新，完成后可导出。": "The list is being updated. Export will be available afterwards.",
  "列表 v{version} 的导出文件已生成": "Export generated for list v{version}",
  导出失败: "Export failed",
} as const;
export const collectionExportText = createTranslator(collectionExportMessages);
