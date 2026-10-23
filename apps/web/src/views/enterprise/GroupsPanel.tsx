import { Pencil, Plus, UsersRound } from "lucide-react";
import { useState } from "react";
import { EmptyState, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseGroup, EnterpriseOperation, EnterpriseUser } from "../../lib/contracts/enterprise";
import { useLocale } from "../../lib/i18n";
import { enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";
import { ModalShell } from "./ModalShell";
import type { GroupAction } from "./types";

export function GroupsPanel({
  groups,
  busy,
  onCreate,
  onAction,
}: {
  groups: EnterpriseGroup[];
  busy: string;
  onCreate: () => void;
  onAction: (action: GroupAction) => void;
}) {
  useLocale();
  return (
    <>
      <div className="section-toolbar">
        <span>{t("{count} 个用户组", { count: groups.length })}</span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          {t("新建用户组")}
        </button>
      </div>
      {groups.length ? (
        <ScrollableTableRegion className="enterprise-table" ariaLabel={t("企业用户组滚动区域")}>
          <table aria-label={t("企业用户组")}>
            <thead>
              <tr>
                <th>{t("用户组")}</th>
                <th>{t("成员")}</th>
                <th>{t("状态")}</th>
                <th>{t("版本")}</th>
                <th aria-label={t("操作")} />
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id}>
                  <td>
                    <strong>{group.name}</strong>
                    <span className="cell-subtitle">{group.description || t("未填写说明")}</span>
                  </td>
                  <td>{group.member_count}</td>
                  <td>
                    <StatusBadge value={group.active ? "active" : "disabled"} />
                  </td>
                  <td>v{group.version}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title={t("编辑用户组")}
                        aria-label={t("编辑 {name}", { name: group.name })}
                        onClick={() => onAction({ group, kind: "edit" })}
                        disabled={Boolean(busy)}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        title={t("管理成员")}
                        aria-label={t("管理 {name} 的成员", { name: group.name })}
                        onClick={() => onAction({ group, kind: "members" })}
                        disabled={Boolean(busy)}
                      >
                        <UsersRound size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <EmptyState title={t("尚未建立用户组")} detail={t("创建用户组以集中维护组织成员。")} />
      )}
    </>
  );
}

export function CreateGroupModal({
  busy,
  close,
  submit,
}: {
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  useLocale();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return (
    <ModalShell title={t("新建用户组")} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit({ kind: "create-group", requestBody: { name: name.trim(), description: description.trim() } });
        }}
      >
        <label>
          {t("用户组名称")}
          <input required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          {t("说明")}
          <textarea maxLength={500} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            {t("取消")}
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            {t("创建用户组")}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

export function GroupActionModal({
  action,
  users,
  busy,
  close,
  submit,
  embedded = false,
}: {
  action: GroupAction;
  users: EnterpriseUser[];
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
  embedded?: boolean;
}) {
  useLocale();
  const [name, setName] = useState(action.group.name);
  const [description, setDescription] = useState(action.group.description);
  const [active, setActive] = useState(action.group.active);
  const [memberIds, setMemberIds] = useState<string[]>(action.group.member_ids);
  const [reason, setReason] = useState("");
  const form = (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit(
          action.kind === "edit"
            ? {
                kind: "update-group",
                groupId: action.group.id,
                requestBody: {
                  expected_version: action.group.version,
                  name: name.trim(),
                  description: description.trim(),
                  active,
                  reason: reason.trim(),
                },
              }
            : {
                kind: "update-group-members",
                groupId: action.group.id,
                requestBody: {
                  expected_version: action.group.version,
                  user_ids: memberIds,
                  reason: reason.trim(),
                },
              },
        );
      }}
    >
      {action.kind === "edit" ? (
        <>
          <label>
            {t("用户组名称")}
            <input required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            {t("说明")}
            <textarea maxLength={500} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label className="check-control">
            <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
            {t("启用用户组")}
          </label>
        </>
      ) : (
        <fieldset className="enterprise-member-list">
          <legend>{action.group.name}</legend>
          {users
            .filter((item) => item.active)
            .map((item) => (
              <label className="check-control" key={item.id}>
                <input
                  type="checkbox"
                  checked={memberIds.includes(item.id)}
                  onChange={(event) =>
                    setMemberIds((current) =>
                      event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id),
                    )
                  }
                />
                <span>
                  {item.display_name} <small>{item.email}</small>
                </span>
              </label>
            ))}
        </fieldset>
      )}
      <label>
        {t("变更原因")}
        <textarea
          required
          minLength={3}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <div className="form-actions">
        <button className="secondary-button" type="button" onClick={close}>
          {t("取消")}
        </button>
        <button className="primary-button" type="submit" disabled={busy}>
          {t("保存变更")}
        </button>
      </div>
    </form>
  );
  return embedded ? (
    form
  ) : (
    <ModalShell title={t("编辑用户组")} close={close}>
      {form}
    </ModalShell>
  );
}
