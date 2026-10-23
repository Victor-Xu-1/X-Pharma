import { formatDate } from "../../components/common";
import type { DataExportJob } from "../../lib/contracts/commercial";
import { OriginalRecordValue, RecordDetails, RecordFacts, RecordList } from "./RecordDetails";

export function ExportRecordDetails({ item }: { item: DataExportJob }) {
  return (
    <RecordDetails name={item.id}>
      <RecordFacts
        fields={[
          { label: "需要审批", value: item.approval_required },
          { label: "审批时间", value: item.approved_at ? formatDate(item.approved_at, true) : null },
          { label: "开始时间", value: item.started_at ? formatDate(item.started_at, true) : null },
          { label: "完成时间", value: item.completed_at ? formatDate(item.completed_at, true) : null },
          { label: "到期时间", value: item.expires_at ? formatDate(item.expires_at, true) : null },
          { label: "原始文件字节", value: item.artifact_bytes },
          { label: "导出字段", value: <RecordList values={item.fields} /> },
          { label: "原始筛选", value: <OriginalRecordValue value={item.filters} /> },
          { label: "失败代码", value: item.failure_code },
          { label: "失败说明", value: item.failure_message },
          { label: "授权标注", value: item.license_attribution },
          { label: "授权策略版本", value: item.license_policy_version },
          { label: "授权策略摘要", value: item.license_policy_sha256 },
          { label: "文件摘要", value: item.artifact_sha256 },
          { label: "清单摘要", value: item.manifest_sha256 },
          { label: "清单密钥标识", value: item.manifest_key_id },
          { label: "清单签名", value: item.manifest_signature },
        ]}
      />
    </RecordDetails>
  );
}
