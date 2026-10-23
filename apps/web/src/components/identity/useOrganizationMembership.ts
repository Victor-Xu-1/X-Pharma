import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { joinOrganization, loadOrganizations, organizationKeys } from "../../lib/contracts/organizations";
import type { OrganizationRead } from "../../lib/generated";
import type { OrganizationControls } from "../OrganizationContext";
import { pendingIdentityMessage, useIdentityOperation } from "./useIdentityOperation";

const readFailure = "请先恢复组织成员资格读取，再提交操作。";
type Feedback = { kind: "success" | "error"; text: string } | null;
function safeFailure(error: unknown, fallback: string, secret?: string) {
  if (error instanceof Error && error.message === pendingIdentityMessage) return error.message;
  if (secret && error instanceof Error && error.message.includes(secret)) return fallback;
  return error instanceof ApiError && [400, 403, 409, 410, 422].includes(error.status) ? error.message : fallback;
}

/** The visible dialog owns local intent; SessionBoundary remains the only organization-switch authority. */
export function useOrganizationMembership(controls: OrganizationControls) {
  const client = useQueryClient();
  const operation = useIdentityOperation();
  const [open, setOpen] = useState(false);
  const [code, setCodeValue] = useState("");
  const [confirmed, setConfirmedValue] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const organizations = useQuery({
    queryKey: organizationKeys.own,
    queryFn: ({ signal }) => loadOrganizations(signal),
    enabled: open,
  });
  const readReady = organizations.isSuccess && !organizations.error && !organizations.isFetching;
  useEffect(() => {
    if (organizations.error instanceof ApiError && [401, 403].includes(organizations.error.status)) {
      setCodeValue("");
      setConfirmedValue(false);
      setFeedback(null);
    }
  }, [organizations.error]);
  function currentReadReady() {
    const state = client.getQueryState(organizationKeys.own);
    return state?.status === "success" && !state.error && state.fetchStatus === "idle";
  }
  function reset() {
    setCodeValue("");
    setConfirmedValue(false);
    setFeedback(null);
  }
  function close() {
    if (operation.isLocked()) return;
    setOpen(false);
    reset();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (operation.isLocked()) return;
    if (!currentReadReady()) {
      setFeedback({ kind: "error", text: readFailure });
      return;
    }
    if (!confirmed || !code.trim() || !event.currentTarget.checkValidity()) return;
    const capturedCode = code.trim();
    let accepted = false;
    await operation.run(
      "join",
      async (current) => {
        const result = await joinOrganization(capturedCode);
        accepted = true;
        if (current()) {
          setCodeValue("");
          setConfirmedValue(false);
          await client.invalidateQueries(
            { queryKey: organizationKeys.own, refetchType: "active" },
            { throwOnError: true },
          );
        }
        return result;
      },
      () => setFeedback({ kind: "success", text: "已加入组织，请从上方选择切换。" }),
      (error) => {
        setCodeValue("");
        setConfirmedValue(false);
        setFeedback(
          accepted
            ? { kind: "success", text: "已加入组织，请重试成员资格读取后再切换。" }
            : { kind: "error", text: safeFailure(error, "邀请接受失败，请重试", capturedCode) },
        );
      },
    );
  }
  async function selectOrganization(id: string) {
    if (operation.isLocked()) return;
    if (!currentReadReady()) {
      setFeedback({ kind: "error", text: readFailure });
      return;
    }
    const target = client.getQueryData<OrganizationRead[]>(organizationKeys.own)?.find((item) => item.tenant_id === id);
    if (!target?.active || target.selected) {
      setFeedback({ kind: "error", text: "组织成员资格已变化，请重新核对后再切换。" });
      return;
    }
    await operation.run(
      "switch",
      () => controls.switchOrganization(id),
      () => {
        setOpen(false);
        reset();
      },
      (error) => setFeedback({ kind: "error", text: safeFailure(error, "组织切换失败，请重试") }),
    );
  }
  return {
    open,
    openPanel: () => {
      if (!operation.isLocked()) setOpen(true);
    },
    close,
    code,
    setCode: (value: string) => {
      if (!operation.isLocked()) {
        setCodeValue(value);
        setFeedback(null);
      }
    },
    confirmed,
    setConfirmed: (value: boolean) => {
      if (!operation.isLocked()) {
        setConfirmedValue(value);
        setFeedback(null);
      }
    },
    operation,
    organizations,
    readReady,
    feedback,
    submit,
    selectOrganization,
  };
}
