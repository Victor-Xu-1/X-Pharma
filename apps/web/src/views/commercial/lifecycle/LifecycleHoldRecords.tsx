import { Check } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { LegalHold } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import { RecordDetails, RecordFacts } from "../RecordDetails";
import type { LifecycleAction } from "./types";
export function LifecycleHoldRecords({
  holds,
  busy,
  beginAction,
}: {
  holds: LegalHold[];
  busy: string;
  beginAction: (action: LifecycleAction) => void;
}) {
  useLocale();
  return (
    <>
      <section className="operations-section">
        <header>
          <div>
            <h2>{t("法律保全记录")}</h2>
          </div>
        </header>
        {!holds.length ? (
          <EmptyState title={t("暂无法律保全记录")} />
        ) : (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("法律保全记录滚动区域")}>
            <table aria-label={t("法律保全记录")}>
              <thead>
                <tr>
                  <th>{t("事项")}</th>
                  <th>{t("范围")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("创建时间")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {holds.map((hold) => (
                  <tr key={hold.id}>
                    <td>
                      <strong>{hold.matter_reference}</strong>
                      <span className="cell-subtitle">{hold.reason}</span>
                      <RecordDetails name={hold.matter_reference}>
                        <RecordFacts
                          fields={[
                            { label: "标识", value: hold.id },
                            { label: "原始保全原因", value: hold.reason },
                            { label: "保全发起人", value: hold.placed_by_user_id },
                            {
                              label: "保全解除时间",
                              value: hold.released_at ? formatDate(hold.released_at, true) : null,
                            },
                            { label: "保全解除人", value: hold.released_by_user_id },
                            { label: "保全解除原因", value: hold.release_reason },
                          ]}
                        />
                      </RecordDetails>
                    </td>
                    <td>
                      {hold.scope_type}
                      <span className="cell-subtitle mono-cell">{hold.scope_id ?? "tenant-wide"}</span>
                    </td>
                    <td>
                      <StatusBadge value={hold.status} />
                    </td>
                    <td>{formatDate(hold.placed_at, true)}</td>
                    <td>
                      {hold.status === "active" ? (
                        <button
                          className="icon-button"
                          type="button"
                          title={t("解除法律保全")}
                          aria-label={t("解除法律保全 {reference}", { reference: hold.matter_reference })}
                          disabled={Boolean(busy)}
                          onClick={() => beginAction({ kind: "release", hold })}
                        >
                          <Check size={17} />
                        </button>
                      ) : (
                        "--"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        )}
      </section>
    </>
  );
}
