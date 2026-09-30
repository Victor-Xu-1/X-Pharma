export interface MoleculeRendering {
  svg: string;
  version: string;
}

interface RenderRequest {
  id: string;
  smiles: string;
}

interface RenderResponse {
  id: string;
  ok: boolean;
  svg?: string;
  version?: string;
  error?: string;
}

interface PendingRendering {
  resolve: (rendering: MoleculeRendering) => void;
  reject: (error: Error) => void;
  timeout: number;
}

const MAX_SMILES_LENGTH = 4_096;
const RENDER_TIMEOUT_MS = 15_000;
const pending = new Map<string, PendingRendering>();
let rendererWorker: Worker | null = null;
let requestSequence = 0;

function failWorker(error: Error): void {
  const failedWorker = rendererWorker;
  rendererWorker = null;
  failedWorker?.terminate();
  for (const rendering of pending.values()) {
    window.clearTimeout(rendering.timeout);
    rendering.reject(error);
  }
  pending.clear();
}

function handleWorkerMessage(event: MessageEvent<unknown>): void {
  const response = event.data as Partial<RenderResponse> | null;
  if (!response || typeof response.id !== "string" || typeof response.ok !== "boolean") return;
  const rendering = pending.get(response.id);
  if (!rendering) return;
  pending.delete(response.id);
  window.clearTimeout(rendering.timeout);
  if (response.ok && typeof response.svg === "string" && typeof response.version === "string") {
    rendering.resolve({ svg: response.svg, version: response.version });
    return;
  }
  rendering.reject(new Error(response.error || "RDKit renderer rejected the structure"));
}

function getWorker(): Worker {
  if (rendererWorker) return rendererWorker;
  const worker = new Worker(new URL("../rdkit.worker.ts", import.meta.url), {
    name: "rdkit-renderer",
    type: "module",
  });
  worker.addEventListener("message", handleWorkerMessage);
  worker.addEventListener("error", () => failWorker(new Error("RDKit renderer is unavailable")));
  rendererWorker = worker;
  return worker;
}

export function renderMolecule(smiles: string): Promise<MoleculeRendering> {
  const normalizedSmiles = smiles.trim();
  if (!normalizedSmiles || normalizedSmiles.length > MAX_SMILES_LENGTH) {
    return Promise.reject(new Error("Structure input is empty or exceeds the rendering limit"));
  }

  let worker: Worker;
  try {
    worker = getWorker();
  } catch {
    return Promise.reject(new Error("RDKit renderer is unavailable"));
  }

  const id = `${Date.now()}-${++requestSequence}`;
  return new Promise<MoleculeRendering>((resolve, reject) => {
    const timeout = window.setTimeout(() => failWorker(new Error("RDKit renderer timed out")), RENDER_TIMEOUT_MS);
    pending.set(id, { resolve, reject, timeout });
    const request: RenderRequest = { id, smiles: normalizedSmiles };
    try {
      worker.postMessage(request);
    } catch {
      pending.delete(id);
      window.clearTimeout(timeout);
      reject(new Error("RDKit renderer is unavailable"));
    }
  });
}
