import { EmptyState } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { probeReadiness } from "../../lib/environmentReadiness";
import type { EnvironmentProbeRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { environmentMessages, environmentProbeStateKeys, environmentSourceText } from "../../lib/i18n/environment";
export function EnvironmentProbeTable({ probes, label }: { probes: EnvironmentProbeRead[]; label: string }) {
  const text = useMessages(environmentMessages);
  if (!probes.length)
    return <EmptyState title={text("暂无探针记录")} detail={text("报告未提供依赖探针，尚不能验证可用性或兼容性。")} />;
  return (
    <ScrollableTableRegion
      className="enterprise-table environment-probe-table"
      ariaLabel={text("{label}（可滚动）", { label })}
    >
      <table aria-label={label}>
        <thead>
          <tr>
            <th>{text("组件")}</th>
            <th>{text("实测值")}</th>
            <th>{text("项目要求")}</th>
            <th>{text("状态")}</th>
          </tr>
        </thead>
        <tbody>
          {probes.map((probe) => {
            const state = probe.status === "present" && !probe.observed ? "unverified" : probe.status;
            const stateLabel =
              probeReadiness([probe]) === "ready"
                ? text("符合已声明要求")
                : Object.hasOwn(environmentProbeStateKeys, state)
                  ? text(environmentProbeStateKeys[state])
                  : state;
            return (
              <tr key={probe.id}>
                <td>{environmentSourceText(probe.label)}</td>
                <td>
                  <code>{probe.observed ? environmentSourceText(probe.observed) : text("未检测到")}</code>
                </td>
                <td>
                  <code>{probe.expected ? environmentSourceText(probe.expected) : text("未声明")}</code>
                </td>
                <td>
                  <span className={`badge environment-status-${state}`}>{stateLabel}</span>
                  {state !== "present" ? <p>{environmentSourceText(probe.detail)}</p> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
