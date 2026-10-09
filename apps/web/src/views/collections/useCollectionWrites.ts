import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/api";
import { type CollectionDetail, collectionsKeys, getComparisonSet } from "../../lib/contracts/collections";
import { useMessages } from "../../lib/i18n";
import { type CollectionMessage, collectionsMessages } from "../../lib/i18n/collections";

type Navigation = (id: string | null, entityIds: string[], replace?: boolean) => void;
type Feedback = { id: string; error: CollectionMessage | { raw: string } | null; notice: CollectionMessage | null };

/** Writes refresh their target, but never take ownership of the current route. */
export function useCollectionWrites(activeId: string, onLocationChange: Navigation) {
  const text = useMessages(collectionsMessages);
  const queryClient = useQueryClient();
  const live = useRef({ id: activeId, epoch: 0, mounted: true, navigate: onLocationChange });
  const lock = useRef(false);
  const [feedback, setFeedback] = useState<Feedback>({ id: activeId, error: null, notice: null });
  useLayoutEffect(() => {
    if (live.current.id !== activeId) live.current.epoch += 1;
    live.current.id = activeId;
    live.current.navigate = onLocationChange;
  });
  useEffect(() => {
    live.current.mounted = true;
    return () => {
      live.current.mounted = false;
      live.current.epoch += 1;
    };
  }, []);
  const mutation = useMutation({ mutationFn: (request: () => Promise<CollectionDetail>) => request() });

  async function write(
    request: () => Promise<CollectionDetail>,
    notice: CollectionMessage | null = null,
    create = false,
  ): Promise<boolean> {
    if (lock.current) return false;
    lock.current = true;
    const target = { id: live.current.id, epoch: live.current.epoch };
    setFeedback({ id: target.id, error: null, notice: null });
    const stillHere = () =>
      live.current.mounted && live.current.epoch === target.epoch && live.current.id === target.id;
    try {
      const next = await mutation.mutateAsync(request);
      queryClient.setQueryData<CollectionDetail>(collectionsKeys.detail(next.id), (current) =>
        current && current.version > next.version ? current : next,
      );
      void queryClient.invalidateQueries({ queryKey: collectionsKeys.catalogs });
      void queryClient.invalidateQueries({ queryKey: collectionsKeys.versions(next.id) });
      if (stillHere()) {
        if (create) live.current.navigate(next.id, []);
        setFeedback({ id: create ? next.id : target.id, error: null, notice });
      }
      return true;
    } catch (caught) {
      const conflict = caught instanceof ApiError && caught.status === 409;
      let refreshed = false;
      if (conflict && target.id) {
        try {
          await queryClient.fetchQuery({
            queryKey: collectionsKeys.detail(target.id),
            queryFn: ({ signal }) => getComparisonSet(target.id, signal),
            staleTime: 0,
          });
          refreshed = true;
        } catch {
          /* Preserve the draft; a failed refresh is not a recovered version. */
        }
      }
      if (stillHere())
        setFeedback({
          id: target.id,
          notice: null,
          error: conflict
            ? refreshed
              ? { key: "列表写入冲突，已刷新当前版本。请核对后重新提交，未自动覆盖。" }
              : { key: "列表版本冲突；当前版本刷新失败，请恢复连接后重新刷新并核对。编辑草稿保留，未自动覆盖。" }
            : caught instanceof Error
              ? { raw: caught.message }
              : { key: "列表写入失败" },
        });
      return false;
    } finally {
      lock.current = false;
    }
  }

  return {
    write,
    pending: mutation.isPending,
    error:
      feedback.id === activeId && feedback.error
        ? "raw" in feedback.error
          ? feedback.error.raw
          : text(feedback.error.key, feedback.error.parameters)
        : "",
    notice: feedback.id === activeId && feedback.notice ? text(feedback.notice.key, feedback.notice.parameters) : "",
  };
}
