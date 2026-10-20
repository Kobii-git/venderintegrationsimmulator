import { useState } from "react";
import { JsonViewer } from "./JsonViewer";
import { copyToClipboard } from "../utils/format";

/** Keep non-JSON evidence readable without escaping its original text. */
export function BodyEvidence({ body, label }: { body: string | null; label: string }) {
  const [notice, setNotice] = useState("");
  if (!body) return <p className="inline-empty">No body recorded.</p>;
  try { return <JsonViewer data={JSON.parse(body) as unknown} label={label} />; } catch { /* Show plain text below. */ }
  return <div><div className="json-toolbar"><strong>{label}</strong><button type="button" className="btn btn-sm" onClick={() => {
    void copyToClipboard(body).then(() => setNotice("Copied body.")).catch(() => setNotice("Clipboard unavailable. Select the body below to copy it."));
  }}>Copy body</button></div>{notice && <p className="form-hint" role="status">{notice}</p>}<pre className="json-viewer" aria-label={label}>{body}</pre></div>;
}
