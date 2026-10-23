import { X } from "lucide-react";
import { FormStatus } from "../../components/FormStatus";
import type { DataSource, DataSourceDataset } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { SourceConnectionFields } from "./SourceConnectionFields";
import { SourceAutomationFields, SourceGovernanceFields } from "./SourceGovernanceFields";
import { useSourceEditorModel } from "./useSourceEditorModel";

export function SourceEditorDialog({
  datasets,
  allowedFolderRoots,
  durableWorkflowsEnabled,
  source,
  onClose,
  onCreated,
}: {
  datasets: DataSourceDataset[];
  allowedFolderRoots: string[];
  durableWorkflowsEnabled: boolean;
  source?: DataSource;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  useLocale();
  const model = useSourceEditorModel({ source, datasets, allowedFolderRoots, onCreated });
  const pending = Boolean(model.operation.busy),
    dismiss = () => {
      if (!model.operation.isLocked()) onClose();
    };
  const dialogRef = useModalFocus<HTMLElement>(true, dismiss, { closeOnEscape: !pending });
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel source-modal"
        role="dialog"
        aria-modal="true"
        aria-busy={pending}
        aria-labelledby="create-source-title"
        tabIndex={-1}
      >
        <header>
          <h2 id="create-source-title">{t(source ? "编辑数据源治理配置" : "接入自动数据源")}</h2>
          <button
            className="icon-button"
            type="button"
            onClick={dismiss}
            disabled={pending}
            title={t("关闭")}
            aria-label={t("关闭")}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <form onSubmit={model.submit}>
          <fieldset className="source-form-fields" disabled={pending}>
            <SourceConnectionFields
              draft={model.draft}
              change={model.change}
              changeType={model.changeType}
              changeAbstract={model.changeAbstract}
              allowedRoots={allowedFolderRoots}
              editing={Boolean(source)}
              durable={durableWorkflowsEnabled}
            />
            <SourceGovernanceFields
              draft={model.draft}
              change={model.change}
              datasets={model.eligibleDatasets}
              source={source}
            />
            <SourceAutomationFields draft={model.draft} change={model.change} />
          </fieldset>
          {!source && !model.eligibleDatasets.length ? (
            <p className="form-error" role="alert">
              {t("当前没有已启用且许可有效的数据集")}
            </p>
          ) : null}
          <FormStatus pending={pending} error={model.operation.error} pendingLabel={t("保存中")} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={dismiss} disabled={pending}>
              {t("取消")}
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={pending || (!source && !model.eligibleDatasets.length)}
            >
              {t(pending ? "保存中" : source ? "保存" : "注册")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
