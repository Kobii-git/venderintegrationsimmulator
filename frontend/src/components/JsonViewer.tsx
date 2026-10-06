import { copyToClipboard } from "../utils/format";

interface JsonViewerProps {
  data: unknown;
  label?: string;
}

export function JsonViewer({ data, label }: JsonViewerProps) {
  const text = JSON.stringify(data, null, 2);

  return (
    <div>
      <div className="json-toolbar">
        {label ? <strong style={{ fontSize: "0.8125rem" }}>{label}</strong> : <span />}
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => void copyToClipboard(text)}
        >
          Copy JSON
        </button>
      </div>
      <pre className="json-viewer">{text}</pre>
    </div>
  );
}

interface JsonEditorProps {
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
}

export function JsonEditor({ value, onChange, error }: JsonEditorProps) {
  return (
    <div className="form-row">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        rows={16}
        aria-invalid={!!error}
      />
      {error ? <span className="form-hint" style={{ color: "var(--danger)" }}>{error}</span> : null}
    </div>
  );
}
