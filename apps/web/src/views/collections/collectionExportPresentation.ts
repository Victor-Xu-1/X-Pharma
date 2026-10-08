import type { CollectionDetail, CollectionPolicy } from "../../lib/contracts/collections";

// Display vocabulary only. The server policy remains the authorization authority.
const fieldCatalog = [
  { value: "position", label: "序号", required: false },
  { value: "id", label: "记录编号", required: true },
  { value: "entity_type", label: "类型", required: true },
  { value: "name", label: "名称", required: true },
  { value: "description", label: "描述", required: false },
  { value: "external_ids", label: "外部标识", required: false },
  { value: "created_at", label: "创建时间", required: false },
  { value: "updated_at", label: "更新时间", required: false },
] as const;

export function collectionExportFields(policy: CollectionPolicy | null | undefined) {
  return (policy?.allowed_fields ?? []).flatMap((value) => {
    const field = fieldCatalog.find((entry) => entry.value === value);
    return field ? [field] : [];
  });
}

export function hasRequiredCollectionFields(fields: readonly string[]) {
  return fieldCatalog.every((field) => !field.required || fields.includes(field.value));
}

export function collectionExportBlockReason(
  detail: CollectionDetail,
  policy: CollectionPolicy | null | undefined,
  { changing, refreshing, stale }: { changing: boolean; refreshing: boolean; stale: boolean },
) {
  if (!policy) return "本组织尚未配置导出策略；请联系管理员。";
  if (!policy.enabled) return "本组织尚未开放列表导出；请联系管理员。";
  if (!hasRequiredCollectionFields(policy.allowed_fields))
    return "导出策略缺少必需字段（记录编号、类型、名称）；请联系管理员核对。";
  if (!Number.isInteger(policy.max_records_per_export) || policy.max_records_per_export < 1)
    return "导出策略的记录上限无效；请联系管理员核对。";
  if (!detail.member_count) return "当前列表尚无可导出对象；先加入关注对象，再导出。";
  if (detail.member_count > policy.max_records_per_export)
    return `列表含 ${detail.member_count} 个对象，超过授权上限 ${policy.max_records_per_export} 个；请先精简列表。`;
  if (stale) return "当前列表刷新失败；请先恢复连接并核对当前版本。";
  if (refreshing) return "正在核对当前列表版本，完成后可导出。";
  if (changing) return "列表正在更新，完成后可导出。";
  return "";
}
