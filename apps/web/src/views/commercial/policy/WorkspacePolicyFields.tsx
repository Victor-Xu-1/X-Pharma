import type { CollectionPolicyDraft } from "../../../lib/contracts/collections";
import { workspacePolicyText as t } from "../../../lib/i18n/workspacePolicy";
import { requiredPolicyFields, workspacePolicyFieldGroups } from "./workspacePolicyFields";
export function WorkspacePolicyFields({
  draft,
  onChange,
}: {
  draft: CollectionPolicyDraft;
  onChange: (next: CollectionPolicyDraft) => void;
}) {
  return (
    <fieldset className="policy-options policy-field-options">
      <legend>{t("允许字段")}</legend>
      {workspacePolicyFieldGroups().map((group) => (
        <details className="policy-field-group" key={group.key} open={group.key === "common"}>
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
