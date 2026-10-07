import { type KeyboardEvent, type ReactNode, useEffect, useRef } from "react";

export type ResearchTabOption<Tab extends string> = {
  key: Tab;
  label: string;
  icon?: ReactNode;
  count?: number;
  disabled?: boolean;
  disabledReason?: string;
  panelId?: string;
};

export function ResearchTabList<Tab extends string>({
  tabs,
  activeTab,
  onChange,
  ariaLabel,
  idPrefix,
  className = "tab-bar",
}: {
  tabs: ReadonlyArray<ResearchTabOption<Tab>>;
  activeTab: Tab;
  onChange: (tab: Tab) => void;
  ariaLabel: string;
  idPrefix: string;
  className?: string;
}) {
  const activeTabRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (activeTabRef.current?.dataset.tabKey === activeTab) {
      activeTabRef.current.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    }
  }, [activeTab]);

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const allButtons = Array.from(
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? [],
    );
    const buttons = allButtons.filter((button) => button.getAttribute("aria-disabled") !== "true");
    const currentIndex = buttons.indexOf(event.currentTarget);
    if (!buttons.length) return;
    event.preventDefault();
    let nextIndex: number;
    if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = buttons.length - 1;
    } else if (currentIndex >= 0) {
      nextIndex = (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    } else {
      const currentPosition = allButtons.indexOf(event.currentTarget);
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextButton = Array.from({ length: allButtons.length }, (_, index) => {
        const candidateIndex = (currentPosition + direction * (index + 1) + allButtons.length) % allButtons.length;
        return allButtons[candidateIndex];
      }).find((button) => button?.getAttribute("aria-disabled") !== "true");
      nextIndex = Math.max(0, buttons.indexOf(nextButton as HTMLButtonElement));
    }
    buttons[nextIndex]?.focus();
    buttons[nextIndex]?.click();
  }

  return (
    <div className={className} role="tablist" aria-label={ariaLabel} aria-orientation="horizontal">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          id={`${idPrefix}-tab-${tab.key}`}
          data-tab-key={tab.key}
          type="button"
          role="tab"
          aria-controls={tab.panelId ?? `${idPrefix}-panel-${tab.key}`}
          aria-selected={activeTab === tab.key}
          aria-disabled={tab.disabled || undefined}
          disabled={Boolean(tab.disabled && activeTab !== tab.key)}
          title={tab.disabled ? (tab.disabledReason ?? "暂无已收录数据") : undefined}
          tabIndex={activeTab === tab.key ? 0 : -1}
          className={activeTab === tab.key ? "active" : ""}
          ref={activeTab === tab.key ? activeTabRef : undefined}
          onClick={() => {
            if (!tab.disabled) onChange(tab.key);
          }}
          onKeyDown={moveFocus}
        >
          {tab.icon}
          {tab.label}
          {tab.count === undefined ? null : `（${tab.count}）`}
        </button>
      ))}
    </div>
  );
}
