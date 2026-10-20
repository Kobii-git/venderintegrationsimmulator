import { useState } from "react";
import { copyToClipboard } from "../utils/format";

interface JsonViewerProps {
  data: unknown;
  label?: string;
}

export function JsonViewer({ data, label }: JsonViewerProps) {
  const text = JSON.stringify(data, null, 2) ?? "null";
  const [message, setMessage] = useState("");

  return (
    <div>
      <div className="json-toolbar">
        {label ? <strong style={{ fontSize: "0.8125rem" }}>{label}</strong> : <span />}
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => {
            setMessage("");
            void copyToClipboard(text).then(() => setMessage("Copied JSON.")).catch(() => setMessage("Clipboard unavailable. Select the text below to copy it."));
          }}
        >
          Copy JSON
        </button>
      </div>
      {message && <p className="form-hint" role="status">{message}</p>}
      <pre className="json-viewer" aria-label={label}>{text}</pre>
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
