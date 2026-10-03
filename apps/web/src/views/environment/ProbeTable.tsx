import type { EnvironmentProbeRead } from "../../lib/generated";

const stateLabels = {
  present: "已检测",
  missing: "未安装",
  mismatch: "版本不符",
  blocked: "检查失败",
  unverified: "尚未验证",
};
export function EnvironmentProbeTable({ probes, label }: { probes: EnvironmentProbeRead[]; label: string }) {
  return (
    <div className="table-frame enterprise-table">
      <table aria-label={label}>
        <thead>
          <tr>
            <th>组件</th>
            <th>实际版本</th>
            <th>项目要求</th>
            <th>状态</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {probes.map((probe) => (
            <tr key={probe.id}>
              <td>{probe.label}</td>
              <td>
                <code>{probe.observed ?? "未检测到"}</code>
              </td>
              <td>
                <code>{probe.expected ?? "以锁文件或部署配置为准"}</code>
              </td>
              <td>
                <span className={`badge environment-status-${probe.status}`}>{stateLabels[probe.status]}</span>
              </td>
              <td>{probe.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
