import type { CollectionPolicyDraft } from "../../../lib/contracts/collections";
import { defaultWorkspacePolicyFields, domainExportCatalog } from "../../../lib/contracts/domainExports";
import { domainExportLabel } from "../../../lib/i18n/domainExport";
import { workspacePolicyText as t } from "../../../lib/i18n/workspacePolicy";

const comparison = {
  position: "序号",
  id: "稳定 ID",
  entity_type: "实体类型",
  name: "名称",
  description: "描述",
  external_ids: "外部标识",
  review_status: "审核状态",
  created_at: "创建时间",
  updated_at: "更新时间",
} as const;
export const requiredPolicyFields = new Set(["id", "entity_type", "name"]);
export function defaultPolicyDraft(): CollectionPolicyDraft {
  return {
    policy_version: "workspace-export-v1",
    enabled: false,
    allowed_formats: ["csv", "json", "xlsx"],
    allowed_fields: [...Object.keys(comparison), ...defaultWorkspacePolicyFields],
    max_records_per_export: 20,
    attribution: "Licensed for internal enterprise use",
  };
}
/** Only catalog-owned labels are localized. Field IDs and licensing payloads remain verbatim. */
export function workspacePolicyFieldGroups() {
  return [
    {
      key: "common",
      label: t("通用字段"),
      fields: Object.entries(comparison).map(([value, label]) => ({ value, label: t(label) })),
    },
    ...Object.entries(domainExportCatalog).map(([key, config]) => ({
      key,
      label: domainExportLabel(config.label),
      fields: config.fields.map((field) => ({ value: key + "." + field.value, label: domainExportLabel(field.label) })),
    })),
  ];
}
