import { Download } from "lucide-react";
import { useState } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { CollectionDetail } from "../../lib/contracts/collections";
import type { ExportFormat } from "../../lib/download";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { collectionExportMessages } from "../../lib/i18n/collectionExport";
import { useDismissibleDetails } from "../../lib/useDismissibleDetails";
import { useCollectionExport } from "./useCollectionExport";

export function CollectionExport({
  detail,
  changing,
  refreshing = false,
  stale = false,
}: {
  detail: CollectionDetail;
  changing: boolean;
  refreshing?: boolean;
  stale?: boolean;
}) {
  const text = useMessages(collectionExportMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const [open, setOpen] = useState(false);
  const control = useCollectionExport(detail, open, { changing, refreshing, stale });
  const popover = useDismissibleDetails({ dismissible: !control.pending });
  const showSettings = Boolean(control.policy?.enabled && !control.reading && !control.policyQuery.isError);
  return (
    <details
      className="domain-export-menu collection-export-menu"
      {...popover}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary aria-disabled={control.pending || undefined}>
        <Download size={15} aria-hidden="true" /> {text("导出列表")}
      </summary>
      {open ? (
        <form
          aria-label={text("列表导出")}
          onSubmit={(event) => {
            event.preventDefault();
            void control.exportSet();
          }}
        >
          <header>
            <strong>{text("列表导出")}</strong>
            {control.canExport || control.pending ? (
              <small>
                {text("最多 {count} 个对象", {
                  count: control.policy ? number.format(control.policy.max_records_per_export) : "—",
                })}
              </small>
            ) : null}
          </header>
          {control.reading && !control.pending ? (
            <FormStatus pending pendingLabel={text("正在读取导出策略")} />
          ) : control.policyQuery.isError && !control.pending ? (
            <>
              <FormStatus
                pending={false}
                error={
                  control.policyQuery.error instanceof Error
                    ? control.policyQuery.error.message
                    : text("导出策略读取失败")
                }
              />
              <button type="button" className="secondary-button" onClick={() => void control.policyQuery.refetch()}>
                {text("重新读取导出策略")}
              </button>
            </>
          ) : (
            <>
              {control.blockReason && !control.pending ? (
                <p className="field-help" role="status">
                  {control.blockReason}
                </p>
              ) : null}
              {showSettings || control.pending ? (
                <>
                  <label>
                    {text("格式")}
                    <select
                      aria-label={text("导出格式")}
                      value={control.format}
                      disabled={control.pending}
                      onChange={(event) => control.setFormat(event.target.value as ExportFormat)}
                    >
                      {control.policy?.allowed_formats.map((value) => (
                        <option value={value} key={value}>
                          {value.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <fieldset className="domain-export-fields" disabled={control.pending}>
                    <legend>{text("导出字段")}</legend>
                    {control.availableFields.map((field) => (
                      <label className="check-control domain-export-field" key={field.value}>
                        <input
                          type="checkbox"
                          checked={control.fields.includes(field.value)}
                          disabled={field.required || control.pending}
                          onChange={(event) => control.toggleField(field.value, event.target.checked)}
                        />
                        {text(field.label)}
                      </label>
                    ))}
                  </fieldset>
                  {control.policy?.attribution ? (
                    <p className="field-help">
                      {text("使用说明：{attribution}", { attribution: control.policy.attribution })}
                    </p>
                  ) : null}
                  <FormStatus
                    pending={control.pending}
                    pendingLabel={text("正在生成列表导出文件")}
                    error={control.error}
                  />
                  {control.notice ? (
                    <p className="inline-feedback" role="status">
                      {control.notice}
                    </p>
                  ) : null}
                  <button className="primary-button" type="submit" disabled={!control.canExport || control.pending}>
                    <Download size={16} aria-hidden="true" />
                    {control.pending ? text("生成中") : text("导出")}
                  </button>
                </>
              ) : null}
            </>
          )}
        </form>
      ) : null}
    </details>
  );
}
