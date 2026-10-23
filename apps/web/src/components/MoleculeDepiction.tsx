import { FlaskConical } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocale } from "../lib/i18n";
import { dossierRecordText as t } from "../lib/i18n/dossierRecords";

import { renderMolecule } from "../lib/rdkitRenderer";

export function MoleculeDepiction({ smiles, name }: { smiles: string; name: string }) {
  useLocale();
  const root = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);
  const [image, setImage] = useState("");
  const [version, setVersion] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const element = root.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "160px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setImage("");
    setFailed(false);
    void renderMolecule(smiles)
      .then(({ svg, version }) => {
        if (!cancelled) {
          setImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
          setVersion(version);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [smiles, visible]);

  return (
    <figure className="molecule-depiction" ref={root} data-rdkit-version={version || undefined}>
      {image ? <img src={image} alt={t("{name} 2D 结构", { name })} /> : null}
      {!image && !failed ? <span className="molecule-loading" role="status" aria-label={t("正在绘制结构")} /> : null}
      {failed ? (
        <span className="molecule-fallback">
          <FlaskConical size={24} />
          <small>{t("结构图不可用")}</small>
        </span>
      ) : null}
    </figure>
  );
}
