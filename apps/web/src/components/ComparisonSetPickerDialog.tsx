import { ListPlus, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import type { CollectionSummary } from "../lib/contracts/collections";
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
}) {
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
          <h2 id="comparison-set-picker-title">加入对比列表</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" disabled={pending}>
            <X size={18} />
          </button>
        </header>
        <p className="modal-context">
          已选择 <strong>{selectedCount}</strong> 个实体
        </p>
        {error ? (
          <p className="inline-error" role="alert">
            {error}
          </p>
        ) : null}
        {loading ? (
          <p className="modal-context" role="status">
            正在读取可编辑列表
          </p>
        ) : sets.length ? (
          <label>
            目标列表
            <select
              value={selectedSetId}
              onChange={(event) => onSetChange(event.target.value)}
              data-modal-autofocus="true"
              required
            >
              {sets.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name} · {item.member_count}/20
                </option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <p className="modal-context">当前没有可编辑的对比列表。直接创建一个新列表，已选择的实体会继续加入其中。</p>
            {onCreateSet ? (
              <>
                <label>
                  新建列表
                  <input
                    type="text"
                    value={newSetName}
                    onChange={(event) => setNewSetName(event.target.value)}
                    placeholder="例如：EGFR 竞品对比"
                    data-modal-autofocus="true"
                    maxLength={120}
                    required
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={newSetShared}
                    onChange={(event) => setNewSetShared(event.target.checked)}
                  />
                  与团队共享
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
                  ? `其中 ${alreadyPresentCount} 个已在列表中，本次将新增 ${effectiveNewCount} 个`
                  : `已选择的 ${alreadyPresentCount} 个实体均已在列表中`}
              </p>
            ) : null}
            <p className={exceedsCapacity ? "inline-error" : "modal-context"}>
              完成后共 {effectiveMemberCount + effectiveNewCount}/20 个实体
            </p>
          </>
        ) : null}
        <footer>
          <button className="secondary-button" type="button" onClick={onClose} disabled={pending}>
            取消
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
            {pending ? "处理中" : selectedSet ? (effectiveNewCount ? "确认加入" : "完成") : "创建并加入"}
          </button>
        </footer>
      </form>
    </div>
  );
}
