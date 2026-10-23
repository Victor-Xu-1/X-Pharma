import type { Dispatch, SetStateAction } from "react";
import type { CollectionPolicyDraft } from "../../../lib/contracts/collections";
import { workspacePolicyText as t } from "../../../lib/i18n/workspacePolicy";
import { requiredPolicyFields, workspacePolicyFieldGroups } from "./workspacePolicyFields";
export function WorkspacePolicyFields({
  draft,
  onChange,
  expandedGroups,
  onExpandedChange,
}: {
  draft: CollectionPolicyDraft;
  onChange: (next: CollectionPolicyDraft) => void;
  expandedGroups: string[];
  onExpandedChange: Dispatch<SetStateAction<string[]>>;
}) {
  const groups = workspacePolicyFieldGroups();
  const knownFields = new Set(groups.flatMap((group) => group.fields.map((field) => field.value)));
  const unknownFields = draft.allowed_fields.filter((field) => !knownFields.has(field));
  return (
    <fieldset className="policy-options policy-field-options">
      <legend>{t("允许字段")}</legend>
      {unknownFields.length ? (
        <div className="policy-unknown-fields">
          <p>{t("以下字段未在当前界面目录中定义，保存时将原样保留。")}</p>
          {unknownFields.map((field) => (
            <code key={field}>{field}</code>
          ))}
        </div>
      ) : null}
      {groups.map((group) => (
        <details
          className="policy-field-group"
          key={group.key}
          open={expandedGroups.includes(group.key)}
          onToggle={(event) => {
            const open = event.currentTarget.open;
            onExpandedChange((current) =>
              current.includes(group.key) === open
                ? current
                : open
                  ? [...current, group.key]
                  : current.filter((key) => key !== group.key),
            );
          }}
        >
          <summary>
            {group.label}
            <span>
              {group.fields.filter((field) => draft.allowed_fields.includes(field.value)).length}/{group.fields.length}
            </span>
          </summary>
          <div>
            {group.fields.map((field) => (
              <label className="check-control" key={field.value}>
                <input
                  type="checkbox"
                  checked={draft.allowed_fields.includes(field.value)}
                  disabled={requiredPolicyFields.has(field.value)}
                  onChange={(event) =>
                    onChange({
                      ...draft,
                      allowed_fields: event.target.checked
                        ? [...draft.allowed_fields, field.value]
                        : draft.allowed_fields.filter((item) => item !== field.value),
                    })
                  }
                />
                {field.label}
              </label>
            ))}
          </div>
        </details>
      ))}
    </fieldset>
  );
}
