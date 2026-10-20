export function ConsoleTabs({ tabs, value, onChange, label, id }: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  label: string; id: string;
}) {
  const prefix = id;
  return <div className="console-tabs" role="tablist" aria-label={label}>
    {tabs.map((tab, index) => <button key={tab.id} id={`${prefix}-tab-${tab.id}`} aria-controls={`${prefix}-panel-${tab.id}`} type="button" role="tab"
      aria-selected={value === tab.id} tabIndex={value === tab.id ? 0 : -1}
      onClick={() => onChange(tab.id)} onKeyDown={(event) => {
        let next = index;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        onChange(tabs[next].id);
        const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button");
        buttons?.[next]?.focus();
      }}>{tab.label}</button>)}
  </div>;
}
