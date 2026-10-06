import type {
  JsonSchemaProperty,
  ObjectJsonSchema,
} from "../../types/api";
import type { VendorOptionValue } from "./vendorOptions";

interface VendorOptionsSectionProps {
  schema?: ObjectJsonSchema;
  value: Record<string, VendorOptionValue>;
  onChange: (value: Record<string, VendorOptionValue>) => void;
}

function inputValue(value: VendorOptionValue | undefined): string | number {
  return typeof value === "boolean" ? "" : (value ?? "");
}

function coerceValue(
  raw: string,
  property: JsonSchemaProperty,
): VendorOptionValue {
  if (property.type === "integer") return Math.trunc(Number(raw));
  if (property.type === "number") return Number(raw);
  return raw;
}

export function VendorOptionsSection({
  schema,
  value,
  onChange,
}: VendorOptionsSectionProps) {
  const properties = Object.entries(schema?.properties ?? {});
  if (properties.length === 0) return null;
  const required = new Set(schema?.required ?? []);

  const update = (name: string, next: VendorOptionValue) => {
    onChange({ ...value, [name]: next });
  };

  return (
    <section className="form-section" aria-labelledby="vendor-options-heading">
      <div id="vendor-options-heading" className="section-title">
        Vendor options
      </div>
      <p className="form-hint">
        Non-secret product settings used to shape discovery, polling, and event responses.
      </p>
      <div className="grid-2">
        {properties.map(([name, property]) => {
          const id = `vendor-option-${name}`;
          const label = property.title ?? name.replaceAll("_", " ");
          if (property.type === "boolean") {
            return (
              <label className="checkbox-item" key={name} htmlFor={id}>
                <input
                  id={id}
                  type="checkbox"
                  checked={Boolean(value[name] ?? property.default ?? false)}
                  onChange={(event) => update(name, event.target.checked)}
                />
                {label}
              </label>
            );
          }
          return (
            <div className="form-row" key={name}>
              <label htmlFor={id}>{label}</label>
              {property.enum ? (
                <select
                  id={id}
                  required={required.has(name)}
                  value={inputValue(value[name] ?? property.default)}
                  onChange={(event) => update(name, coerceValue(event.target.value, property))}
                >
                  {!required.has(name) ? <option value="">Not set</option> : null}
                  {property.enum.map((option) => (
                    <option key={String(option)} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={id}
                  required={required.has(name)}
                  type={property.type === "number" || property.type === "integer" ? "number" : "text"}
                  min={property.minimum}
                  max={property.maximum}
                  minLength={property.minLength}
                  maxLength={property.maxLength}
                  pattern={property.pattern}
                  value={inputValue(value[name] ?? property.default)}
                  onChange={(event) => update(name, coerceValue(event.target.value, property))}
                />
              )}
              {property.description ? (
                <span className="form-hint">{property.description}</span>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
