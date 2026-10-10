import { type FormEvent, useMemo, useState } from "react";
import type { DataSource, DataSourceDataset } from "../../lib/contracts/dataFactory";
import { createDataSource, updateDataSource } from "../../lib/contracts/dataFactory";
import type { DataSourceCreate } from "../../lib/generated";
import {
  initialSourceEditorDraft,
  type SourceEditorDraft,
  sourceAuthorizationScopes,
  sourceEditorPayload,
} from "./sourceEditorDraft";
import { initialPublicSourceDraft, isPublicResearchSource, PUBLIC_RESEARCH_SOURCES } from "./sourceRules";
import { useFactoryOperation } from "./useFactoryOperation";

export function useSourceEditorModel({
  source,
  datasets,
  allowedFolderRoots,
  onCreated,
}: {
  source?: DataSource;
  datasets: readonly DataSourceDataset[];
  allowedFolderRoots: readonly string[];
  onCreated: () => Promise<void>;
}) {
  const eligibleDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.active && dataset.license_current),
    [datasets],
  );
  const [draft, setDraft] = useState(() => initialSourceEditorDraft(source, eligibleDatasets, allowedFolderRoots));
  const operation = useFactoryOperation();
  function change<K extends keyof SourceEditorDraft>(key: K, value: SourceEditorDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function changeType(sourceType: DataSource["source_type"]) {
    setDraft((current) => {
      if (isPublicResearchSource(sourceType)) {
        const definition = PUBLIC_RESEARCH_SOURCES[sourceType];
        const datasetKey =
          sourceType === "pubmed" ? "literature" : sourceType === "chembl" ? "chembl" : "clinical_trials";
        return {
          ...current,
          sourceType,
          rootUri: definition.rootUri,
          classification: "public",
          authorizationScopes: definition.authorizationScope,
          datasetKey: eligibleDatasets.some((dataset) => dataset.dataset_key === datasetKey)
            ? datasetKey
            : current.datasetKey,
          routing: initialPublicSourceDraft(),
          credentialRef: "",
        };
      }
      const rootUri =
        sourceType === "folder"
          ? (allowedFolderRoots[0] ?? "/sources/knowledge")
          : sourceType === "http_manifest"
            ? "https://supplier.example/v1/manifest"
            : sourceType === "s3_snapshot"
              ? "s3://licensed-supplier/research/"
              : sourceType === "sftp_snapshot"
                ? "sftp://supplier.example:22/delivery/"
                : "smb://fileserver.example:445/research/delivery/";
      return { ...current, sourceType, rootUri, credentialRef: "" };
    });
  }
  function changeAbstract(include: boolean) {
    setDraft((current) => {
      const scope = "public:ncbi-pubmed-abstracts",
        scopes = sourceAuthorizationScopes(current.authorizationScopes).filter((value) => value !== scope);
      if (include) scopes.push(scope);
      return {
        ...current,
        routing: { ...current.routing, includeAbstract: include },
        authorizationScopes: scopes.join("\n"),
      };
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    await operation.execute(source ? `source:${source.id}:edit` : "source:create", "注册失败", async (current) => {
      const payload = sourceEditorPayload(draft, source);
      if (source) await updateDataSource(source.id, payload);
      else await createDataSource(payload as DataSourceCreate);
      if (current()) await onCreated();
    });
  }
  return { draft, change, changeType, changeAbstract, eligibleDatasets, submit, operation };
}
