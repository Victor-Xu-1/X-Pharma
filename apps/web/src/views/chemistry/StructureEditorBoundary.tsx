import { Component, type ReactNode } from "react";
import { chemistryText as t } from "../../lib/i18n/chemistry";

export class StructureEditorBoundary extends Component<
  { children: ReactNode; onFallback: () => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="structure-editor-fallback" role="alert">
          <strong>{t("结构画板加载失败")}</strong>
          <button className="secondary-button" type="button" onClick={this.props.onFallback}>
            {t("改用高级输入")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
