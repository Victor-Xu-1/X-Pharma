import type { ColumnDef } from "@tanstack/react-table";
import { AddToComparisonControl } from "../../components/AddToComparisonControl";
import { ClinicalTrialLandscape } from "../../components/ClinicalTrialLandscape";
import { EmptyQueryResult } from "../../components/EmptyQueryResult";
import { QueryResultSummary } from "../../components/QueryResultSummary";
import { ResultPagination } from "../../components/ResultPagination";
import { type SortingState, VirtualDataTable } from "../../components/VirtualDataTable";
import type { TrialSavedSearchInput } from "../../lib/contracts/trials";
import type { ClinicalTrialSearchItemRead, ClinicalTrialSearchResult } from "../../lib/generated";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { publicCoverageNotice } from "../../lib/publicWarnings";
import { TrialResultActions } from "./TrialResultActions";

const PAGE_SIZE = 100;
const defaultTrialSorting: SortingState = [{ id: "last_update_posted", desc: true }];
export function TrialSearchResults({
  data,
  refreshing,
  onRefresh,
  input,
  displayMode,
  analysisView,
  onDisplayModeChange,
  onAnalysisViewChange,
  onSave,
  onLandscapeFilter,
  columns,
  sorting,
  onSortingChange,
  selectedRowIds,
  selectedEntityIds,
  onSelectionChange,
  onComparisonAdded,
  onClear,
  onPageChange,
}: {
  data: ClinicalTrialSearchResult;
  refreshing: boolean;
  onRefresh: () => void;
  input: TrialSavedSearchInput;
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onAnalysisViewChange: (view: "chart" | "table") => void;
  onSave: () => void;
  onLandscapeFilter: (field: "phase" | "result_evaluation", value: string) => void;
  columns: ColumnDef<ClinicalTrialSearchItemRead>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  selectedRowIds: readonly string[];
  selectedEntityIds: string[];
  onSelectionChange: (rows: string[]) => void;
  onComparisonAdded: (message: string) => void;
  onClear: () => void;
  onPageChange: (offset: number) => void;
}) {
  return (
    <div className="domain-results">
      <div className="pipeline-result-toolbar">
        <QueryResultSummary
          total={data.total}
          offset={data.offset}
          count={data.items.length}
          unit={t("项临床试验")}
          queriedAt={data.as_of}
        />
        <TrialResultActions
          refreshing={refreshing}
          onRefresh={onRefresh}
          displayMode={displayMode}
          onDisplayModeChange={onDisplayModeChange}
          input={input}
          onSave={onSave}
          totalRows={data.total}
        />
      </div>
      {data.total && displayMode === "landscape" ? (
        <ClinicalTrialLandscape
          landscape={data.landscape}
          onFilter={onLandscapeFilter}
          view={analysisView}
          onViewChange={onAnalysisViewChange}
        />
      ) : data.items.length ? (
        <VirtualDataTable
          ariaLabel={t("临床试验结果")}
          columns={columns}
          data={data.items}
          getRowId={(trial) => trial.id}
          preferenceKey="clinical-trials"
          totalRows={data.total}
          sorting={sorting}
          defaultSorting={defaultTrialSorting}
          onSortingChange={onSortingChange}
          sortingScope="all"
          toolbarActions={<AddToComparisonControl selectedEntityIds={selectedEntityIds} onAdded={onComparisonAdded} />}
          rowSelection={{
            selectedRowIds,
            onChange: onSelectionChange,
            getRowLabel: (trial) => t("对比 {registry}", { registry: trial.registry_id }),
            label: t("选择对比试验"),
            maxSelectedRows: 20,
          }}
        />
      ) : (
        <EmptyQueryResult domain={t("临床试验")} filtered={Boolean(data.applied_filters?.length)} onClear={onClear} />
      )}
      {displayMode === "list" ? (
        <ResultPagination
          totalRows={data.total}
          offset={data.offset}
          pageSize={PAGE_SIZE}
          notice={publicCoverageNotice(data.warnings)}
          onPageChange={onPageChange}
          ariaLabel={t("临床试验结果分页")}
        />
      ) : (
        <footer className="pipeline-landscape-footer">
          <span>{publicCoverageNotice(data.warnings)}</span>
        </footer>
      )}
    </div>
  );
}
