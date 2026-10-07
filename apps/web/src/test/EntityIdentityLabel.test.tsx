import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EntityIdentityLabel } from "../components/EntityIdentityLabel";

it("keeps the registration qualification explicit while disclosing the full source note on demand", () => {
  render(
    <EntityIdentityLabel
      entity={{ entity_type: "disease", attributes: { identity_scope: "provider_label" }, name: "Registry condition" }}
    />,
  );
  expect(screen.getByText("登记条件")).toBeVisible();
  const note = screen.getByText("注册平台的研究条件名称，尚未完成本体标准化，不代表获批适应症。");
  expect(note).not.toBeVisible();
  fireEvent.click(screen.getByLabelText("Registry condition 的身份说明"));
  expect(note).toBeVisible();
});

it("does not add an explanation control for a canonical record", () => {
  render(<EntityIdentityLabel entity={{ entity_type: "target", attributes: {}, name: "Reviewed target" }} />);
  expect(screen.getByText("靶点")).toBeVisible();
  expect(screen.queryByText("身份说明")).not.toBeInTheDocument();
});
