import type { DuplicateMode } from "../../types/api";

export interface FaultControlsState {
  enabled: boolean;
  removeTimestamp: boolean;
  invalidTimestamp: boolean;
  malformedJson: boolean;
  timestampMode: "current" | "fixed" | "offset";
  timestampFixedValue: string;
  timestampFieldPaths: string;
  offsetAmount: number;
  offsetUnit: "minutes" | "hours" | "days";
  offsetDirection: "past" | "future";
  removeFields: string;
  nullFields: string;
  extraFieldKey: string;
  extraFieldValue: string;
  largeFieldPath: string;
  largeFieldSizeKb: number;
  duplicateMode: DuplicateMode;
  sourceEventId: string;
  preDelayMs: number;
  timeoutSeconds: number;
  duplicateSendCount: number;
  retryCount: number;
  retryDelayMs: number;
}

interface FaultControlsSectionProps {
  value: FaultControlsState;
  onChange: <K extends keyof FaultControlsState>(
    key: K,
    value: FaultControlsState[K],
  ) => void;
}

export function FaultControlsSection({ value, onChange }: FaultControlsSectionProps) {
  return (
    <section className="form-section" aria-labelledby="fault-controls-heading">
      <div id="fault-controls-heading" className="section-title">
        Fault / Edge Case Simulation
      </div>
      <p className="form-hint">
        Deliberately generate problematic telemetry to test collector ingestion. Disabled by
        default.
      </p>
      <label className="checkbox-item">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(event) => onChange("enabled", event.target.checked)}
        />
        <strong>Enable fault injection</strong>
      </label>
      {value.enabled ? (
        <>
          <div className="grid-2">
            <FaultToggle
              label="Remove timestamp fields"
              checked={value.removeTimestamp}
              onChange={(checked) => onChange("removeTimestamp", checked)}
            />
            <FaultToggle
              label="Invalid timestamp"
              checked={value.invalidTimestamp}
              onChange={(checked) => onChange("invalidTimestamp", checked)}
            />
            <FaultToggle
              label="Malformed JSON body"
              checked={value.malformedJson}
              onChange={(checked) => onChange("malformedJson", checked)}
            />
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Timestamp mode</label>
              <select
                value={value.timestampMode}
                onChange={(event) =>
                  onChange(
                    "timestampMode",
                    event.target.value as FaultControlsState["timestampMode"],
                  )
                }
              >
                <option value="current">Current (UTC)</option>
                <option value="fixed">Fixed timestamp</option>
                <option value="offset">Offset</option>
              </select>
            </div>
            {value.timestampMode === "fixed" ? (
              <div className="form-row">
                <label>Fixed timestamp</label>
                <input
                  type="datetime-local"
                  value={value.timestampFixedValue}
                  onChange={(event) => onChange("timestampFixedValue", event.target.value)}
                />
              </div>
            ) : null}
            {value.timestampMode === "offset" ? (
              <>
                <div className="form-row">
                  <label>Offset amount</label>
                  <input
                    type="number"
                    min={1}
                    value={value.offsetAmount}
                    onChange={(event) => onChange("offsetAmount", Number(event.target.value))}
                  />
                </div>
                <div className="form-row">
                  <label>Offset unit</label>
                  <select
                    value={value.offsetUnit}
                    onChange={(event) =>
                      onChange(
                        "offsetUnit",
                        event.target.value as FaultControlsState["offsetUnit"],
                      )
                    }
                  >
                    <option value="minutes">Minutes</option>
                    <option value="hours">Hours</option>
                    <option value="days">Days</option>
                  </select>
                </div>
                <div className="form-row">
                  <label>Direction</label>
                  <select
                    value={value.offsetDirection}
                    onChange={(event) =>
                      onChange(
                        "offsetDirection",
                        event.target.value as FaultControlsState["offsetDirection"],
                      )
                    }
                  >
                    <option value="past">Past</option>
                    <option value="future">Future</option>
                  </select>
                </div>
              </>
            ) : null}
          </div>
          <TextField
            label="Timestamp target fields (comma-separated dot paths)"
            placeholder="notification.createdAt, event.timestamp"
            value={value.timestampFieldPaths}
            onChange={(next) => onChange("timestampFieldPaths", next)}
            hint="Leave blank to use the selected product scenario defaults."
          />
          <TextField
            label="Remove fields (comma-separated dot paths)"
            placeholder="notification.context.Title"
            value={value.removeFields}
            onChange={(next) => onChange("removeFields", next)}
          />
          <TextField
            label="Null fields (comma-separated dot paths)"
            placeholder="notification.context.Domain"
            value={value.nullFields}
            onChange={(next) => onChange("nullFields", next)}
          />
          <div className="grid-2">
            <TextField
              label="Extra field key"
              value={value.extraFieldKey}
              onChange={(next) => onChange("extraFieldKey", next)}
            />
            <TextField
              label="Extra field value"
              value={value.extraFieldValue}
              onChange={(next) => onChange("extraFieldValue", next)}
            />
          </div>
          <div className="grid-2">
            <TextField
              label="Large field path"
              value={value.largeFieldPath}
              onChange={(next) => onChange("largeFieldPath", next)}
            />
            <div className="form-row">
              <label>Large field size (KB)</label>
              <input
                type="number"
                min={1}
                max={512}
                value={value.largeFieldSizeKb}
                onChange={(event) => onChange("largeFieldSizeKb", Number(event.target.value))}
              />
            </div>
          </div>
          <div className="section-title">Duplicate testing</div>
          <div className="grid-2">
            <div className="form-row">
              <label>Duplicate mode</label>
              <select
                value={value.duplicateMode}
                onChange={(event) => onChange("duplicateMode", event.target.value as DuplicateMode)}
              >
                <option value="none">None</option>
                <option value="exact_payload">Exact duplicate payload</option>
                <option value="duplicate_correlation_id">Duplicate correlation ID</option>
                <option value="repeat_scenario_new_ids">Repeat scenario (new IDs)</option>
              </select>
            </div>
            <TextField
              label="Source event ID"
              value={value.sourceEventId}
              onChange={(next) => onChange("sourceEventId", next)}
            />
          </div>
          <div className="section-title">Delivery behaviour</div>
          <div className="grid-2">
            <NumberField
              label="Pre-delivery delay (ms)"
              min={0}
              value={value.preDelayMs}
              onChange={(next) => onChange("preDelayMs", next)}
            />
            <NumberField
              label="Timeout override (seconds)"
              min={1}
              max={300}
              value={value.timeoutSeconds}
              onChange={(next) => onChange("timeoutSeconds", next)}
            />
            <NumberField
              label="Duplicate send count"
              min={1}
              max={3}
              value={value.duplicateSendCount}
              onChange={(next) => onChange("duplicateSendCount", next)}
            />
            <NumberField
              label="Retry on failure"
              min={0}
              max={3}
              value={value.retryCount}
              onChange={(next) => onChange("retryCount", next)}
            />
            <NumberField
              label="Retry delay (ms)"
              min={0}
              max={30000}
              value={value.retryDelayMs}
              onChange={(next) => onChange("retryDelayMs", next)}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}

function FaultToggle({ label, checked, onChange }: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="checkbox-item">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function TextField({ label, value, onChange, placeholder, hint }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  return (
    <div className="form-row">
      <label>{label}</label>
      <input
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <span className="form-hint">{hint}</span> : null}
    </div>
  );
}

function NumberField({ label, value, min, max, onChange }: {
  label: string;
  value: number;
  min: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="form-row">
      <label>{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}
