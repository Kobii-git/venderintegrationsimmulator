import { useEffect, useState } from "react";

import type { ScenarioSummary } from "../types/api";

type Overrides = Record<string, Record<string, unknown>>;

interface Props {
  scenarios: ScenarioSummary[];
  selectedIds: string[];
  value: Overrides;
  onChange: (value: Overrides) => void;
}

interface JsonFieldProps {
  id: string;
  value: unknown;
  fallback: unknown;
  onChange: (value: unknown) => void;
}

function JsonField({ id, value, fallback, onChange }: JsonFieldProps) {
  const effective = value ?? fallback ?? (Array.isArray(fallback) ? [] : {});
  const [draft, setDraft] = useState(() => JSON.stringify(effective, null, 2));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(JSON.stringify(value ?? fallback ?? {}, null, 2));
    setError(null);
  }, [fallback, value]);

  return (
    <>
      <textarea
        id={id}
        rows={5}
        className={error ? "input-error" : undefined}
        value={draft}
        onChange={(event) => {
          const next = event.target.value;
          setDraft(next);
          try {
            onChange(JSON.parse(next) as unknown);
            setError(null);
            event.target.setCustomValidity("");
          } catch {
            setError("Enter valid JSON before saving.");
            event.target.setCustomValidity("Enter valid JSON.");
          }
        }}
      />
      {error ? <span className="field-error">{error}</span> : null}
    </>
  );
}

export function ScenarioOverridesSection({
  scenarios,
  selectedIds,
  value,
  onChange,
}: Props) {
  const updateField = (scenarioId: string, field: string, next: unknown) => {
    onChange({
      ...value,
      [scenarioId]: { ...(value[scenarioId] ?? {}), [field]: next },
    });
  };

  const selected = scenarios.filter((scenario) => selectedIds.includes(scenario.id));
  if (!selected.length) return null;

  return (
    <div className="scenario-overrides">
      <div className="section-title">Scenario configuration</div>
      {selected.map((scenario) => {
        const schema = scenario.config_schema as {
          properties?: Record<
            string,
            {
              type?: string;
              title?: string;
              description?: string;
              default?: unknown;
              enum?: unknown[];
            }
          >;
          required?: string[];
        };
        const properties = schema.properties ?? {};
        const required = new Set(schema.required ?? []);
        return (
          <fieldset className="scenario-fieldset" key={scenario.id}>
            <legend>{scenario.display_name}</legend>
            {Object.entries(properties).length === 0 ? (
              <p className="form-hint">This scenario has no configurable values.</p>
            ) : null}
            {Object.entries(properties).map(([name, property]) => {
              const id = `scenario-${scenario.id}-${name}`;
              const current = value[scenario.id]?.[name];
              const displayValue = current ?? property.default ?? "";
              const label = property.title ?? name;
              return (
                <div className="form-row" key={name}>
                  <label htmlFor={id}>
                    {label} {required.has(name) ? <span aria-label="required">*</span> : null}
                  </label>
                  {property.enum ? (
                    <select
                      id={id}
                      required={required.has(name)}
                      value={String(displayValue)}
                      onChange={(event) => updateField(scenario.id, name, event.target.value)}
                    >
                      {property.enum.map((option) => (
                        <option key={String(option)} value={String(option)}>
                          {String(option)}
                        </option>
                      ))}
                    </select>
                  ) : property.type === "boolean" ? (
                    <label className="checkbox-item">
                      <input
                        id={id}
                        type="checkbox"
                        checked={Boolean(displayValue)}
                        onChange={(event) =>
                          updateField(scenario.id, name, event.target.checked)
                        }
                      />
                      Enabled
                    </label>
                  ) : property.type === "integer" || property.type === "number" ? (
                    <input
                      id={id}
                      type="number"
                      step={property.type === "integer" ? 1 : "any"}
                      required={required.has(name)}
                      value={String(displayValue)}
                      onChange={(event) =>
                        updateField(
                          scenario.id,
                          name,
                          property.type === "integer"
                            ? Number.parseInt(event.target.value, 10)
                            : Number(event.target.value),
                        )
                      }
                    />
                  ) : property.type === "array" || property.type === "object" ? (
                    <JsonField
                      id={id}
                      value={current}
                      fallback={property.default}
                      onChange={(next) => updateField(scenario.id, name, next)}
                    />
                  ) : (
                    <input
                      id={id}
                      required={required.has(name)}
                      value={String(displayValue)}
                      onChange={(event) => updateField(scenario.id, name, event.target.value)}
                    />
                  )}
                  {property.description ? (
                    <span className="form-hint">{property.description}</span>
                  ) : null}
                  {property.default !== undefined ? (
                    <span className="form-hint">
                      Default: <code>{JSON.stringify(property.default)}</code>
                    </span>
                  ) : null}
                </div>
              );
            })}
          </fieldset>
        );
      })}
    </div>
  );
}
