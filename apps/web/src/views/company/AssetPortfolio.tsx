import { Pill } from "lucide-react";
import { EmptyState, StatusBadge } from "../../components/common";
import type { CompanyDossier } from "../../lib/contracts/company";
import { useLocale } from "../../lib/i18n";
import { companyDossierText as t } from "../../lib/i18n/companyDossier";
import { localizedFullDevelopmentPhase } from "../../lib/i18n/programVocabulary";
import { type LoadedCompanyAsset, loadedCompanyAssets } from "./assets";

function AssetRows({ assets, onOpenDrug }: { assets: LoadedCompanyAsset[]; onOpenDrug: (id: string) => void }) {
  return (
    <ol className="company-asset-list company-asset-portfolio" aria-label={t("已返回研发资产")}>
      {assets.map((asset) => (
        <li key={asset.id}>
          <button type="button" onClick={() => onOpenDrug(asset.id)}>
            {asset.name}
          </button>
          <span>{asset.modalities.join(t("、")) || t("模态未披露")}</span>
          <dl className="company-asset-phases">
            <dt className="sr-only">{t("已记录项目阶段")}</dt>
            <dd>
              {asset.phases.map((phase) => (
                <StatusBadge key={phase} value={phase} label={localizedFullDevelopmentPhase(phase)} />
              ))}
            </dd>
          </dl>
        </li>
      ))}
    </ol>
  );
}
export function AssetPortfolio({ data, onOpenDrug }: { data: CompanyDossier; onOpenDrug: (id: string) => void }) {
  useLocale();
  const assets = loadedCompanyAssets(data.programs);
  return (
    <section className="company-profile-section">
      <header>
        <div>
          <h3>{t("主要研发资产")}</h3>
        </div>
        <Pill size={18} />
      </header>
      {assets.length ? (
        <>
          <p className="company-asset-context">{t("阶段来自本次返回的研发项目，不代表药物的单一全球阶段。")}</p>
          <AssetRows assets={assets.slice(0, 8)} onOpenDrug={onOpenDrug} />
          {assets.length > 8 ? (
            <details className="company-assets-disclosure">
              <summary>{t("更多已返回资产（{count}）", { count: assets.length - 8 })}</summary>
              <AssetRows assets={assets.slice(8)} onOpenDrug={onOpenDrug} />
            </details>
          ) : null}
        </>
      ) : (
        <EmptyState title={t("暂无已发布研发资产")} />
      )}
    </section>
  );
}
