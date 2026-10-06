import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
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
    <ScrollableTableRegion className="enterprise-table" ariaLabel={`${label}（可滚动）`}>
      <table aria-label={label}>
        <thead>
          <tr>
            <th>组件</th>
            <th>实际版本</th>
            <th>项目要求</th>
            <th>状态</th>
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
                <code>{probe.expected ?? "未声明"}</code>
              </td>
              <td>
                <span className={`badge environment-status-${probe.status}`}>
                  {probe.status === "present" && probe.expected ? "符合已声明要求" : stateLabels[probe.status]}
                </span>
                {probe.status !== "present" ? <p>{probe.detail}</p> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
