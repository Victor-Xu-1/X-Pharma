import type { MainModule } from "@rdkit/rdkit";
import rdkitWasmUrl from "@rdkit/rdkit/RDKit_minimal.wasm?url";

interface RenderRequest {
  id: string;
  smiles: string;
}

type RenderResponse = { id: string; ok: true; svg: string; version: string } | { id: string; ok: false; error: string };

const MAX_SMILES_LENGTH = 4_096;
let modulePromise: Promise<MainModule> | null = null;

function loadRDKit(): Promise<MainModule> {
  if (!modulePromise) {
    modulePromise = import("@rdkit/rdkit")
      .then((module) => module.default({ locateFile: () => rdkitWasmUrl }))
      .catch((error: unknown) => {
        modulePromise = null;
        throw error;
      });
  }
  return modulePromise;
}

function respond(response: RenderResponse): void {
  self.postMessage(response);
}

self.addEventListener("message", (event: MessageEvent<unknown>) => {
  const request = event.data as Partial<RenderRequest> | null;
  if (
    !request ||
    typeof request.id !== "string" ||
    typeof request.smiles !== "string" ||
    !request.smiles ||
    request.smiles.length > MAX_SMILES_LENGTH
  ) {
    if (request && typeof request.id === "string") {
      respond({ id: request.id, ok: false, error: "Invalid structure input" });
    }
    return;
  }

  const id = request.id;
  const smiles = request.smiles;
  void loadRDKit()
    .then((rdkit) => {
      const molecule = rdkit.get_mol(smiles);
      if (!molecule) throw new Error("RDKit rejected the structure");
      try {
        respond({
          id,
          ok: true,
          svg: molecule.get_svg(360, 180),
          version: rdkit.version(),
        });
      } finally {
        molecule.delete();
      }
    })
    .catch(() => {
      respond({ id, ok: false, error: "RDKit could not render the structure" });
    });
});
