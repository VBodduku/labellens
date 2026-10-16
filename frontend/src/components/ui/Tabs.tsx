import { m } from "motion/react";
import { useRef, type KeyboardEvent } from "react";
import { panelId, tabId } from "./tabIds";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  badge?: number;
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  idPrefix: string;
}

/** Accessible tab list (arrow keys, Home/End) with a gliding underline. Pair each panel with `panelId`. */
export function Tabs<T extends string>({ tabs, value, onChange, label, idPrefix }: TabsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = tabs.findIndex((tab) => tab.id === value);
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight" ? (current + 1) % tabs.length
      : event.key === "ArrowLeft" ? (current - 1 + tabs.length) % tabs.length
      : event.key === "Home" ? 0
      : event.key === "End" ? last
      : null;
    if (next === null) return;
    event.preventDefault();
    const tab = tabs[next];
    if (tab) {
      onChange(tab.id);
      refs.current[next]?.focus();
    }
  }

  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="-mx-1 flex overflow-x-auto border-b border-line px-1">
      {tabs.map((tab, index) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(node) => {
              refs.current[index] = node;
            }}
            id={tabId(idPrefix, tab.id)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId(idPrefix, tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={`relative flex min-h-12 shrink-0 items-center gap-1.5 px-3 text-sm font-semibold transition-colors duration-fast ${
              selected ? "text-text" : "text-text-dim hover:text-text"
            }`}
          >
            {tab.label}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="hatch flex min-w-5 items-center justify-center rounded-chip px-1.5 text-[0.7rem] font-bold text-unknown shadow-[inset_0_0_0_1px_var(--unknown)]">
                {tab.badge}
              </span>
            )}
            {selected && (
              <m.span
                layoutId={`${idPrefix}-underline`}
                className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-[var(--beam-gradient)]"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
