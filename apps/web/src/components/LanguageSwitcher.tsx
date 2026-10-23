import { Languages } from "lucide-react";
import { useId } from "react";
import { setLocale, t, useLocale } from "../lib/i18n";
import { isLocale } from "../lib/i18n/locale";
import "./LanguageSwitcher.css";

export function LanguageSwitcher() {
  const { locale, persistence } = useLocale();
  const noticeId = useId();
  return (
    <div className="language-switcher">
      <label>
        <Languages size={16} aria-hidden="true" />
        <span className="sr-only">{t("界面语言")}</span>
        <select
          value={locale}
          aria-describedby={persistence === "unavailable" ? noticeId : undefined}
          onChange={(event) => {
            if (isLocale(event.target.value)) setLocale(event.target.value);
          }}
        >
          <option value="zh-CN" lang="zh-CN">
            中文
          </option>
          <option value="en" lang="en">
            English
          </option>
        </select>
      </label>
      {persistence === "unavailable" ? (
        <small id={noticeId} role="status">
          {t("语言已切换，但浏览器未允许保存；关闭页面后可能需要重新选择。")}
        </small>
      ) : null}
    </div>
  );
}
