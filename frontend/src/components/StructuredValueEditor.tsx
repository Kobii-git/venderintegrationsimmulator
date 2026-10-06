import type { ConfiguredValue } from "../types/api";

interface Props {
  label: string;
  value: ConfiguredValue[];
  onChange: (value: ConfiguredValue[]) => void;
  namePlaceholder?: string;
}

const forcedSensitive = (name: string) =>
  /^(authorization|proxy-authorization|cookie|set-cookie)$/i.test(name) ||
  /(password|passwd|secret|token|api[-_]?key|code)/i.test(name);

export function StructuredValueEditor({
  label,
  value,
  onChange,
  namePlaceholder = "Name",
}: Props) {
  const update = (index: number, patch: Partial<ConfiguredValue>) => {
    onChange(
      value.map((entry, entryIndex) => {
        if (entryIndex !== index) return entry;
        const next = { ...entry, ...patch };
        if (forcedSensitive(next.name)) next.sensitive = true;
        return next;
      }),
    );
  };

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= value.length) return;
    const next = [...value];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <div className="form-row">
      <label>{label}</label>
      <div className="structured-values">
        {value.map((entry, index) => {
          const locked = forcedSensitive(entry.name);
          return (
            <div className="structured-value-row" key={index}>
              <input
                aria-label={`${label} name ${index + 1}`}
                placeholder={namePlaceholder}
                value={entry.name}
                onChange={(event) => update(index, { name: event.target.value })}
              />
              <input
                aria-label={`${label} value ${index + 1}`}
                type={entry.sensitive ? "password" : "text"}
                placeholder={
                  entry.sensitive && entry.has_value && !entry.value
                    ? "Stored — enter to replace"
                    : "Value"
                }
                value={entry.value ?? ""}
                onChange={(event) => update(index, { value: event.target.value })}
                autoComplete="new-password"
              />
              <label className="checkbox-item compact-checkbox">
                <input
                  type="checkbox"
                  checked={entry.sensitive}
                  disabled={locked}
                  onChange={(event) => update(index, { sensitive: event.target.checked })}
                />
                Sensitive
              </label>
              <div className="inline-actions">
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => move(index, -1)}
                  disabled={index === 0}
                  aria-label={`Move ${entry.name || "entry"} up`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => move(index, 1)}
                  disabled={index === value.length - 1}
                  aria-label={`Move ${entry.name || "entry"} down`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="btn btn-small btn-danger"
                  onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
        <button
          type="button"
          className="btn btn-small"
          onClick={() => onChange([...value, { name: "", sensitive: true }])}
        >
          Add entry
        </button>
      </div>
      <span className="form-hint">
        Sensitive values are encrypted and write-only. New entries default to sensitive.
      </span>
    </div>
  );
}
