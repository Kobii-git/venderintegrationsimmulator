interface KeyValueEditorProps {
  label: string;
  value: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}

export function KeyValueEditor({
  label,
  value,
  onChange,
  keyPlaceholder = "Header name",
  valuePlaceholder = "Value",
}: KeyValueEditorProps) {
  const entries = Object.entries(value);

  const update = (index: number, key: string, val: string) => {
    const rows = entries.length ? [...entries] : [["", ""]];
    rows[index] = [key, val];
    const next: Record<string, string> = {};
    for (const [k, v] of rows) {
      if (k.trim()) next[k.trim()] = v;
    }
    onChange(next);
  };

  const addRow = () => {
    onChange({ ...value, "": "" });
  };

  const removeRow = (index: number) => {
    const rows = [...entries];
    rows.splice(index, 1);
    const next: Record<string, string> = {};
    for (const [k, v] of rows) {
      if (k.trim()) next[k.trim()] = v;
    }
    onChange(next);
  };

  const rows = entries.length ? entries : [["", ""]];

  return (
    <div className="form-row">
      <label>{label}</label>
      <div className="kv-editor">
        {rows.map(([k, v], index) => (
          <div className="kv-row" key={index}>
            <input
              placeholder={keyPlaceholder}
              value={k}
              onChange={(e) => update(index, e.target.value, v)}
            />
            <input
              placeholder={valuePlaceholder}
              value={v}
              onChange={(e) => update(index, k, e.target.value)}
            />
            <button type="button" className="btn btn-sm" onClick={() => removeRow(index)}>
              ✕
            </button>
          </div>
        ))}
        <button type="button" className="btn btn-sm" onClick={addRow}>
          + Add row
        </button>
      </div>
    </div>
  );
}
