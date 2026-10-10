import { CircleAlert } from "lucide-react";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";

/** An early link to the existing status panel; no duplicated query or queue counts. */
export function FactoryProjectionAlert({ onInspect }: { onInspect: () => void }) {
  useLocale();
  return (
    <div className="factory-warning factory-projection-alert" role="status">
      <CircleAlert size={17} aria-hidden="true" />
      <strong>{t("检索投影需要关注")}</strong>
      <button type="button" className="text-button" onClick={onInspect}>
        {t("查看运行状态")}
      </button>
    </div>
  );
}
