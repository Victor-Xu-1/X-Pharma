import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { createPortal } from "react-dom";

import { joinOrganization, loadOrganizations, organizationKeys } from "../lib/contracts/organizations";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, Spinner } from "./common";
import { type OrganizationControls, useOrganizationControls } from "./OrganizationContext";
import "./OrganizationPanel.css";

export function OrganizationPanel() {
  const controls = useOrganizationControls();
  return controls ? <MembershipPanel controls={controls} /> : null;
}

function MembershipPanel({ controls }: { controls: OrganizationControls }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState("");
  const focus = useModalFocus<HTMLDivElement>(open, close);
  const organizations = useQuery({
    queryKey: organizationKeys.own,
    queryFn: ({ signal }) => loadOrganizations(signal),
    enabled: open,
  });
  const join = useMutation({
    mutationFn: joinOrganization,
    onSuccess: async () => {
      setCode("");
      setConfirmed(false);
      await client.invalidateQueries({ queryKey: organizationKeys.own });
    },
    onError: () => setCode(""),
  });

  function close() {
    setOpen(false);
    setCode("");
    setConfirmed(false);
    join.reset();
    setSwitchError("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (confirmed && code.trim()) join.mutate(code.trim());
  }

  async function selectOrganization(id: string) {
    setSwitching(true);
    setSwitchError("");
    try {
      await controls.switchOrganization(id);
      close();
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : "组织切换失败，请重试");
    } finally {
      setSwitching(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="nav-button"
        onClick={() => setOpen(true)}
        aria-label="组织与账号"
        title="组织与账号"
      >
        <Building2 size={18} aria-hidden="true" />
        <span className="sidebar-account-copy">
          <strong>组织与账号</strong>
          {controls.organizationName ? (
            <small title={controls.organizationName}>{controls.organizationName}</small>
          ) : null}
        </span>
      </button>
      {open
        ? createPortal(
            <div className="modal-backdrop">
              <div
                ref={focus}
                className="modal-panel organization-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="organization-title"
                tabIndex={-1}
              >
                <header className="modal-header">
                  <h2 id="organization-title">组织与账号</h2>
                  <button type="button" className="secondary-button" onClick={close}>
                    关闭
                  </button>
                </header>
                <p>每次会话只访问一个组织。切换不会合并或转移研究、数据、授权与历史记录。</p>
                {organizations.isPending ? (
                  <Spinner label="正在读取组织成员资格" />
                ) : organizations.error ? (
                  <ErrorState message="组织成员资格读取失败" retry={() => void organizations.refetch()} />
                ) : organizations.data?.length ? (
                  <ul className="permission-list">
                    {organizations.data.map((organization) => (
                      <li key={organization.tenant_id}>
                        <strong>{organization.name}</strong>
                        <span>
                          {organization.role} ·{" "}
                          {organization.selected ? "当前组织" : organization.active ? "可切换" : "已停用"}
                        </span>
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={!organization.active || organization.selected || switching || join.isPending}
                          onClick={() => void selectOrganization(organization.tenant_id)}
                        >
                          切换到 {organization.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState title="没有组织成员资格" detail="请联系组织管理员获取邀请码。" />
                )}
                {switchError ? (
                  <p role="alert" className="form-error">
                    {switchError}
                  </p>
                ) : null}
                <form className="modal-form" onSubmit={submit}>
                  <h3>接受组织邀请</h3>
                  <label>
                    <span>管理员邀请码</span>
                    <input
                      type="password"
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      autoComplete="off"
                      spellCheck={false}
                      maxLength={2048}
                      required
                    />
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      required
                    />
                    <span>我确认加入邀请的组织，原组织的数据不会共享。</span>
                  </label>
                  {join.error ? (
                    <p role="alert" className="form-error">
                      {join.error instanceof Error ? join.error.message : "邀请接受失败，请重试"}
                    </p>
                  ) : null}
                  {join.isSuccess ? <p role="status">已加入组织，请从上方选择切换。</p> : null}
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={!code.trim() || !confirmed || join.isPending || switching}
                  >
                    {join.isPending ? "接受中…" : "确认加入组织"}
                  </button>
                </form>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
