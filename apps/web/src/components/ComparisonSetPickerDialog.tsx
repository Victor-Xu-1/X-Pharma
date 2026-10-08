import { ListPlus, X } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import type { CollectionSummary } from "../lib/contracts/collections";
import { useMessages } from "../lib/i18n";
import { comparisonMessages } from "../lib/i18n/comparison";
import { useModalFocus } from "../lib/useModalFocus";

export function ComparisonSetPickerDialog({
  open,
  selectedCount,
  alreadyPresentCount = 0,
  newSelectedCount,
  selectedSetMemberCount,
  sets,
  selectedSetId,
  loading,
  pending,
  error,
  onSetChange,
  onClose,
  onSubmit,
  onCreateSet,
  catalogControls,
}: {
  open: boolean;
  selectedCount: number;
  alreadyPresentCount?: number;
  newSelectedCount?: number;
  selectedSetMemberCount?: number;
  sets: CollectionSummary[];
  selectedSetId: string;
  loading: boolean;
  pending: boolean;
  error: string;
  onSetChange: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCreateSet?: (name: string, visibility: "private" | "tenant") => void | Promise<void>;
  catalogControls?: ReactNode;
}) {
  const t = useMessages(comparisonMessages);
  const dialogRef = useModalFocus<HTMLFormElement>(open, onClose, { closeOnEscape: !pending });
  const [newSetName, setNewSetName] = useState("");
  const [newSetShared, setNewSetShared] = useState(false);

  useEffect(() => {
    if (!open) return;
    setNewSetName("");
    setNewSetShared(false);
  }, [open]);

  if (!open) return null;
  const selectedSet = sets.find((item) => item.id === selectedSetId) ?? null;
  const effectiveNewCount = newSelectedCount ?? selectedCount;
  const effectiveMemberCount = selectedSetMemberCount ?? selectedSet?.member_count ?? 0;
  const exceedsCapacity = Boolean(selectedSet && effectiveMemberCount + effectiveNewCount > 20);
  const canCreateSet = Boolean(onCreateSet && newSetName.trim());

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (pending) {
      event.preventDefault();
      return;
    }
    if (!selectedSet && onCreateSet) {
      event.preventDefault();
      if (canCreateSet) void onCreateSet(newSetName.trim(), newSetShared ? "tenant" : "private");
      return;
    }
    onSubmit(event);
  }

  return (
    <div className="modal-scrim" role="presentation">
      <form
        ref={dialogRef}
        className="workspace-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comparison-set-picker-title"
        tabIndex={-1}
        onSubmit={handleSubmit}
      >
        <header>
          <h2 id="comparison-set-picker-title">{t("加入对比列表")}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={pending}>
            <X size={18} />
          </button>
        </header>
        <p className="modal-context">{t("已选择 {count} 个实体", { count: selectedCount })}</p>
        {error ? (
          <p className="inline-error" role="alert">
            {error}
          </p>
        ) : null}
        {catalogControls}
        {loading ? (
          <p className="modal-context" role="status">
            {t("正在读取可编辑列表")}
          </p>
        ) : sets.length || selectedSetId ? (
          <label>
            {t("目标列表")}
            <select
              value={selectedSetId}
              onChange={(event) => onSetChange(event.target.value)}
              data-modal-autofocus="true"
              required
              disabled={pending}
            >
              {selectedSetId && !selectedSet ? (
                <option value={selectedSetId} disabled>
                  {t("当前列表不可访问，请选择其他列表")}
                </option>
              ) : null}
              {sets.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name} · {item.member_count}/20
                </option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <p className="modal-context">{t("当前目录没有可选择的列表。可调整搜索，或创建新列表后加入已选实体。")}</p>
            {onCreateSet ? (
              <>
                <label>
                  {t("新建列表")}
                  <input
                    type="text"
                    value={newSetName}
                    onChange={(event) => setNewSetName(event.target.value)}
                    placeholder={t("例如：EGFR 竞品对比")}
                    data-modal-autofocus="true"
                    maxLength={120}
                    required
                    disabled={pending}
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={newSetShared}
                    disabled={pending}
                    onChange={(event) => setNewSetShared(event.target.checked)}
                  />
                  {t("与团队共享")}
                </label>
              </>
            ) : null}
          </>
        )}
        {selectedSet ? (
          <>
            {alreadyPresentCount ? (
              <p className="modal-context">
                {effectiveNewCount
                  ? t("其中 {existing} 个已在列表中，本次将新增 {added} 个", {
                      existing: alreadyPresentCount,
                      added: effectiveNewCount,
                    })
                  : t("已选择的 {count} 个实体均已在列表中", { count: alreadyPresentCount })}
              </p>
            ) : null}
            <p className={exceedsCapacity ? "inline-error" : "modal-context"}>
              {t("完成后共 {count}/20 个实体", { count: effectiveMemberCount + effectiveNewCount })}
            </p>
          </>
        ) : null}
        <footer>
          <button className="secondary-button" type="button" onClick={onClose} disabled={pending}>
            {t("取消")}
          </button>
          <button
            className="primary-button"
            type={selectedSet ? "submit" : "button"}
            disabled={pending || loading || (selectedSet ? exceedsCapacity : !canCreateSet)}
            onClick={
              selectedSet || !onCreateSet
                ? undefined
                : () => void onCreateSet(newSetName.trim(), newSetShared ? "tenant" : "private")
            }
          >
            <ListPlus size={16} />
            {t(pending ? "处理中" : selectedSet ? (effectiveNewCount ? "确认加入" : "完成") : "创建并加入")}
          </button>
        </footer>
      </form>
    </div>
  );
}
