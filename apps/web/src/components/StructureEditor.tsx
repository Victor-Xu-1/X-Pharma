import type { Ketcher } from "ketcher-core";
import { type ButtonsConfig, Editor } from "ketcher-react";
import "ketcher-react/dist/index.css";
import { StandaloneStructServiceProvider } from "ketcher-standalone/dist/binaryWasm";
import { Check, Eraser } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { applyStructureEditorAccessibility } from "../lib/structureEditorAccessibility";
import { isStructureApplyDisabled } from "../lib/structureEditorState";

const simplifiedButtons: ButtonsConfig = {
  about: { hidden: true },
  arrows: { hidden: true },
  "create-monomer": { hidden: true },
  "enhanced-stereo": { hidden: true },
  fullscreen: { hidden: true },
  help: { hidden: true },
  miew: { hidden: true },
  recognize: { hidden: true },
  "reaction-arrow-both-ends-filled-triangle": { hidden: true },
  "reaction-arrow-dashed-open-angle": { hidden: true },
  "reaction-arrow-elliptical-arc-arrow-filled-bow": { hidden: true },
  "reaction-arrow-elliptical-arc-arrow-filled-triangle": { hidden: true },
  "reaction-arrow-elliptical-arc-arrow-open-angle": { hidden: true },
  "reaction-arrow-elliptical-arc-arrow-open-half-angle": { hidden: true },
  "reaction-arrow-equilibrium-filled-half-bow": { hidden: true },
  "reaction-arrow-equilibrium-filled-triangle": { hidden: true },
  "reaction-arrow-equilibrium-open-angle": { hidden: true },
  "reaction-arrow-failed": { hidden: true },
  "reaction-arrow-filled-bow": { hidden: true },
  "reaction-arrow-filled-triangle": { hidden: true },
  "reaction-arrow-open-angle": { hidden: true },
  "reaction-arrow-unbalanced-equilibrium-filled-half-bow": { hidden: true },
  "reaction-arrow-unbalanced-equilibrium-filled-half-triangle": { hidden: true },
  "reaction-arrow-unbalanced-equilibrium-large-filled-half-bow": { hidden: true },
  "reaction-arrow-unbalanced-equilibrium-open-half-angle": { hidden: true },
  "reaction-automap": { hidden: true },
  "reaction-map": { hidden: true },
  "reaction-mapping-tools": { hidden: true },
  "reaction-plus": { hidden: true },
  "reaction-unmap": { hidden: true },
  rgroup: { hidden: true },
  "rgroup-attpoints": { hidden: true },
  "rgroup-fragment": { hidden: true },
  "rgroup-label": { hidden: true },
  sgroup: { hidden: true },
  shape: { hidden: true },
  "shape-ellipse": { hidden: true },
  "shape-line": { hidden: true },
  "shape-rectangle": { hidden: true },
  text: { hidden: true },
};

const STRUCTURE_SERIALIZATION_TIMEOUT_MS = 15_000;

function withTimeout<T>(operation: Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(
      () => reject(new Error("Structure serialization timed out")),
      STRUCTURE_SERIALIZATION_TIMEOUT_MS,
    );
    operation.then(
      (value) => {
        window.clearTimeout(timeoutId);
        resolve(value);
      },
      (error: unknown) => {
        window.clearTimeout(timeoutId);
        reject(error);
      },
    );
  });
}

export function StructureEditor({
  value,
  format,
  onApply,
  onError,
}: {
  value: string;
  format: "smiles" | "smarts";
  onApply: (value: string) => void;
  onError: (message: string) => void;
}) {
  const provider = useMemo(() => new StandaloneStructServiceProvider(), []);
  const editorRootRef = useRef<HTMLDivElement | null>(null);
  const ketcherRef = useRef<Ketcher | null>(null);
  const lastLoadedValue = useRef("");
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hasStructure, setHasStructure] = useState(Boolean(value.trim()));
  const [status, setStatus] = useState("正在准备结构画板");

  const refreshStructureAvailability = useCallback(async () => {
    const ketcher = ketcherRef.current;
    if (!ketcher) return;
    try {
      const structure = await withTimeout(format === "smarts" ? ketcher.getSmarts() : ketcher.getSmiles());
      setHasStructure(Boolean(structure.trim()));
    } catch {
      // Keep the last known state when the editor is still serializing a change.
    }
  }, [format]);

  useEffect(() => {
    const root = editorRootRef.current;
    if (!root) return;
    applyStructureEditorAccessibility(root);
    const observer = new MutationObserver(() => applyStructureEditorAccessibility(root));
    observer.observe(root, { characterData: true, childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const root = editorRootRef.current;
    if (!root || !ready) return;
    let frameId: number | null = null;
    const scheduleRefresh = () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        void refreshStructureAvailability();
      });
    };
    const events = ["pointerup", "keyup", "paste", "cut", "drop"] as const;
    events.forEach((eventName) => {
      root.addEventListener(eventName, scheduleRefresh);
    });
    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      events.forEach((eventName) => {
        root.removeEventListener(eventName, scheduleRefresh);
      });
    };
  }, [ready, refreshStructureAvailability]);

  useEffect(() => {
    const ketcher = ketcherRef.current;
    if (!ready || !ketcher || value === lastLoadedValue.current) return;
    lastLoadedValue.current = value;
    setHasStructure(Boolean(value.trim()));
    setStatus(value ? "正在载入结构" : "可以开始绘制");
    void ketcher
      .setMolecule(value, { needZoom: true })
      .then(() => {
        setHasStructure(Boolean(value.trim()));
        setStatus(value ? "结构已载入，可继续编辑" : "可以开始绘制");
      })
      .catch(() => {
        setStatus("结构载入失败");
        onError("无法载入当前结构，请检查内容后重试。");
      });
  }, [onError, ready, value]);

  async function initialize(ketcher: Ketcher) {
    ketcherRef.current = ketcher;
    setReady(true);
    if (!value) {
      setHasStructure(false);
      setStatus("可以开始绘制");
      return;
    }
    lastLoadedValue.current = value;
    setHasStructure(Boolean(value.trim()));
    try {
      await ketcher.setMolecule(value, { needZoom: true });
      setHasStructure(true);
      setStatus("结构已载入，可继续编辑");
    } catch {
      setStatus("结构载入失败");
      onError("无法载入当前结构，请检查内容后重试。");
    }
  }

  async function applyStructure() {
    const ketcher = ketcherRef.current;
    if (!ketcher) return;
    setBusy(true);
    setStatus("正在读取结构");
    try {
      const structure = await withTimeout(format === "smarts" ? ketcher.getSmarts() : ketcher.getSmiles());
      const normalized = structure.trim();
      if (!normalized) {
        setHasStructure(false);
        onError("请先在画板中绘制结构。");
        setStatus("画板中尚无结构");
        return;
      }
      lastLoadedValue.current = normalized;
      setHasStructure(true);
      onApply(normalized);
      setStatus("结构已用于本次检索");
    } catch {
      onError("无法读取当前结构，请检查结构后重试。");
      setStatus("结构读取失败");
    } finally {
      setBusy(false);
    }
  }

  async function clearStructure() {
    const ketcher = ketcherRef.current;
    if (!ketcher) return;
    setBusy(true);
    try {
      await ketcher.setMolecule("");
      lastLoadedValue.current = "";
      setHasStructure(false);
      onApply("");
      setStatus("画板已清空");
    } catch {
      onError("无法清空画板，请刷新页面后重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="structure-editor" aria-label="结构式编辑器">
      <div className="structure-editor-canvas" ref={editorRootRef}>
        <Editor
          staticResourcesUrl={import.meta.env.BASE_URL}
          structServiceProvider={provider}
          errorHandler={() => onError("结构编辑器无法处理当前操作，请调整结构后重试。")}
          onInit={(ketcher) => void initialize(ketcher)}
          buttons={simplifiedButtons}
          disableMacromoleculesEditor
        />
      </div>
      <footer className="structure-editor-actions">
        <span role="status">{status}</span>
        <div>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void clearStructure()}
            disabled={!ready || busy}
          >
            <Eraser size={16} />
            清空画板
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={() => void applyStructure()}
            disabled={isStructureApplyDisabled({ ready, busy, hasStructure })}
            title={!hasStructure && ready ? "请先在画板中绘制结构" : undefined}
          >
            <Check size={16} />
            应用到检索
          </button>
        </div>
      </footer>
    </section>
  );
}
