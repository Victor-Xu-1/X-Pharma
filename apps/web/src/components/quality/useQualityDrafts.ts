import { useState } from "react";
export type QualityDraft = { ownerId?: string; notes?: string };
/** The mounted workspace owns unsent drafts; inactive sections do not issue quality reads. */
export function useQualityDrafts() {
  const [status, setStatus] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, QualityDraft>>({});
  return { status, setStatus, selectedId, setSelectedId, drafts, setDrafts };
}
export type QualityDraftState = ReturnType<typeof useQualityDrafts>;
