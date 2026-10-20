import { useEffect, useRef, useState } from "react";
import { post } from "../api/client";
import type { AuthConfigInput, DestinationConfig } from "../types/api";
import { formatApiError } from "../utils/format";

export function AzureDestinationEditor({
  destination,
  auth,
  onChange,
  testRecord,
}: {
  destination: DestinationConfig;
  auth: AuthConfigInput;
  onChange: (destination: DestinationConfig, auth: AuthConfigInput) => void;
  testRecord?: Record<string, unknown>;
}) {
  const relay = destination.transport_id === "azure_function_app";
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const version = useRef(0);
  useEffect(() => { version.current += 1; setResult(""); setBusy(false); }, [destination, auth, testRecord]);
  useEffect(() => () => { version.current += 1; }, []);
  const check = async (send: boolean) => {
    const requestId = ++version.current;
    setBusy(true); setResult("");
    try {
      const response = await post(
        `/transport/azure/${send ? "send" : "test"}`,
        {
          destination,
          auth_config: auth,
          ...(send
            ? {
                record: testRecord ?? {
                  TimeGenerated: new Date().toISOString(),
                  SourceProfile: "uploaded-logs",
                  Computer: "simulator",
                  RawData: "Explicit ingestion test record",
                },
              }
            : {}),
        },
      );
      if (requestId === version.current) setResult(JSON.stringify(response, null, 2));
    } catch (e) {
      if (requestId === version.current) setResult(formatApiError(e));
    } finally {
      if (requestId === version.current) setBusy(false);
    }
  };
  return (
    <div className="azure-editor">
      <p className="form-hint">
        {relay
          ? "Function App forwards to its configured DCE, DCR and stream using managed identity. Enter the /api/ingest URL."
          : "Grant this application's service principal Monitoring Metrics Publisher on the DCR."}{" "}
        Secrets are encrypted when saved. Blank secret fields keep stored
        values; these checks require entering credentials.
      </p>
      {(relay
        ? [["url", "Function ingestion URL"]]
        : [
            ["endpoint", "DCE endpoint"],
            ["tenant_id", "Tenant ID"],
            ["dcr_immutable_id", "DCR immutable ID"],
            ["stream", "Stream name"],
          ]
      ).map(([key, label]) => (
        <div className="form-row" key={key}>
          <label>
            {label}
            <input
              aria-label={label}
              type={key === "url" || key === "endpoint" ? "url" : "text"}
              required
              value={String(destination[key as keyof DestinationConfig] ?? "")}
              onChange={(e) =>
                onChange({ ...destination, [key]: e.target.value }, auth)
              }
            />
          </label>
        </div>
      ))}
      {!relay && (
        <div className="form-row">
          <label>
            Client ID
            <input
              required
              value={auth.oauth_client_id ?? ""}
              onChange={(e) =>
                onChange(destination, {
                  ...auth,
                  oauth_client_id: e.target.value,
                })
              }
            />
          </label>
        </div>
      )}
      <div className="form-row">
        <label>
          {relay ? "Function key" : "Client secret"}
          <input
            type="password"
            autoComplete="new-password"
            placeholder="Blank keeps stored secret"
            value={(relay ? auth.token : auth.oauth_client_secret) ?? ""}
            onChange={(e) =>
              onChange(destination, {
                ...auth,
                [relay ? "token" : "oauth_client_secret"]:
                  e.target.value || undefined,
              })
            }
          />
        </label>
      </div>
      <p>
        API acceptance does not confirm table arrival. Retrying or resending
        after an uncertain response can create duplicates.
      </p>
      <button
        type="button"
        className="btn"
        disabled={busy}
        onClick={() => void check(false)}
      >
        Check authentication
      </button>{" "}
      <button
        type="button"
        className="btn"
        disabled={busy}
        onClick={() => void check(true)}
      >
        Send test record
      </button>
      <p className="form-hint">
        Authentication checks send no logs. Send test record uploads the first
        validated record, or a custom-table test envelope when no preview is
        available.
      </p>
      {result && <pre className="json-viewer" aria-label="Connection result">{result}</pre>}
    </div>
  );
}
