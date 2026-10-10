import { ArrowUpRight, Check, Copy } from "lucide-react";
import { useState } from "react";
import { EmptyState, formatDate } from "../../components/common";
import { MoleculeDepiction } from "../../components/MoleculeDepiction";
import type { ChemistrySearchHit, ChemistrySearchResult } from "../../lib/contracts/chemistry";
import { useLocale } from "../../lib/i18n";
import { chemistryModeKeys as modeLabels, chemistryText as t } from "../../lib/i18n/chemistry";

export function ChemistryResults({
  result,
  busy,
  failed,
  onInspectEntity,
}: {
  result: ChemistrySearchResult | undefined;
  busy: boolean;
  failed: boolean;
  onInspectEntity: (entityId: string) => void;
}) {
  useLocale();
  return (
    <div className="chemistry-results" aria-busy={busy}>
      {!result && !busy && !failed ? <EmptyState title={t("尚未执行结构查询")} /> : null}
      {result ? (
        <>
          <header className="chemistry-result-head">
            <div>
              <strong>{result.count}</strong>
              <span>{t("{mode}命中", { mode: t(modeLabels[result.mode]) })}</span>
            </div>
            <dl>
              <div>
                <dt>{t("检索结构")}</dt>
                <dd>
                  <code>{result.normalized_query}</code>
                </dd>
              </div>
              <div>
                <dt>{t("查询时间")}</dt>
                <dd title={t("本次结构查询时间，不代表来源数据的最后更新时间")}>{formatDate(result.as_of, true)}</dd>
              </div>
            </dl>
          </header>
          {result.items.length ? (
            <div className="chemistry-hit-list">
              {result.items.map((item) => (
                <ChemistryHitRow key={item.id} item={item} onInspectEntity={onInspectEntity} />
              ))}
            </div>
          ) : (
            <EmptyState title={t("没有符合条件的结构")} />
          )}
        </>
      ) : null}
    </div>
  );
}

function ChemistryHitRow({
  item,
  onInspectEntity,
}: {
  item: ChemistrySearchHit;
  onInspectEntity: (entityId: string) => void;
}) {
  const [copied, setCopied] = useState<"smiles" | "key" | null>(null);

  async function copy(value: string, field: "smiles" | "key") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(field);
      window.setTimeout(() => setCopied((current) => (current === field ? null : current)), 1200);
    } catch {
      setCopied(null);
    }
  }

  return (
    <article className="chemistry-hit">
      <MoleculeDepiction smiles={item.canonical_smiles} name={item.entity_name} />
      <div className="chemistry-hit-core">
        <header>
          <div>
            <h3>{item.entity_name}</h3>
            <code>{item.standard_inchi_key}</code>
          </div>
          {item.similarity !== null ? (
            <strong className="similarity-score">
              {(item.similarity * 100).toFixed(1)}
              <small>%</small>
            </strong>
          ) : null}
        </header>
        <dl className="chemistry-properties">
          <div>
            <dt>{t("分子式")}</dt>
            <dd>{item.molecular_formula ?? "--"}</dd>
          </div>
          <div>
            <dt>{t("分子量")}</dt>
            <dd>{number(item.molecular_weight)}</dd>
          </div>
          <div>
            <dt>{t("精确质量")}</dt>
            <dd>{number(item.exact_mass)}</dd>
          </div>
          <div>
            <dt>{t("更新时间")}</dt>
            <dd>{formatDate(item.updated_at)}</dd>
          </div>
        </dl>
        <div className="structure-identifiers">
          <div>
            <span>SMILES</span>
            <code>{item.canonical_smiles}</code>
            <button
              className="icon-button"
              type="button"
              title={t("复制 SMILES")}
              aria-label={t("复制 {name} SMILES", { name: item.entity_name })}
              onClick={() => void copy(item.canonical_smiles, "smiles")}
            >
              {copied === "smiles" ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
          <div>
            <span>InChIKey</span>
            <code>{item.standard_inchi_key}</code>
            <button
              className="icon-button"
              type="button"
              title={t("复制 InChIKey")}
              aria-label={t("复制 {name} InChIKey", { name: item.entity_name })}
              onClick={() => void copy(item.standard_inchi_key, "key")}
            >
              {copied === "key" ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
        </div>
        <footer>
          <button className="text-button" type="button" onClick={() => onInspectEntity(item.entity_id)}>
            {t("查看实体")} <ArrowUpRight size={14} />
          </button>
        </footer>
      </div>
    </article>
  );
}

function number(value: number | null): string {
  return value === null ? "--" : String(value);
}
