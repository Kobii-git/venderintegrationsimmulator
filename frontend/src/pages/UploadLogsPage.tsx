import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, request } from "../api/client";
import {
  createSimulation,
  getSimulation,
  startSimulation,
  stopSimulation,
} from "../api/simulations";
import { AzureDestinationEditor } from "../components/AzureDestinationEditor";
import { ErrorAlert } from "../components/ErrorAlert";
import type {
  AuthConfigInput,
  Dataset,
  DestinationConfig,
  SimulationResponse,
} from "../types/api";
import { formatApiError } from "../utils/format";

type Validation = {
  record_count: number;
  records: Record<string, unknown>[];
  payload_mode: string;
  schema_verified: boolean;
};
export function UploadLogsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [format, setFormat] = useState("ndjson");
  const [mode, setMode] = useState("envelope");
  const [rewrite, setRewrite] = useState(false);
  const [rate, setRate] = useState(10);
  const [destination, setDestination] = useState<DestinationConfig>({
    transport_id: "azure_logs_ingestion",
    timeout_seconds: 30,
  });
  const [auth, setAuth] = useState<AuthConfigInput>({ auth_method_id: "none" });
  const [validation, setValidation] = useState<Validation | null>(null);
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    void get<Dataset[]>("/datasets")
      .then(setDatasets)
      .catch((e) => setError(formatApiError(e)));
  }, []);
  useEffect(() => {
    setValidation(null);
  }, [datasetId, mode, rewrite]);
  useEffect(() => {
    if (
      !simulation ||
      (simulation.status !== "running" &&
        !simulation.targets?.some((t) => Number(t.stats.queued ?? 0) > 0))
    )
      return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void getSimulation(simulation.id)
        .then((s) => {
          if (!cancelled) setSimulation(s);
        })
        .catch((e) => {
          if (!cancelled) setError(formatApiError(e));
        });
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [simulation]);
  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const dataset = await request<Dataset>(
        `/datasets?name=${encodeURIComponent(file.name)}&format=${format}`,
        {
          method: "POST",
          body: file,
          headers: { "Content-Type": "application/octet-stream" },
        },
      );
      setDatasets((ds) => [dataset, ...ds]);
      setDatasetId(dataset.id);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  const validate = () =>
    post<Validation>(`/datasets/${datasetId}/validate-ingestion`, {
      payload_mode: mode,
      rewrite_timestamps: rewrite,
    });
  const preview = async () => {
    setBusy(true);
    setError(null);
    setValidation(null);
    try {
      setValidation(await validate());
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const checked = await validate();
      setValidation(checked);
      const created = await createSimulation({
        name: `Upload: ${datasets.find((d) => d.id === datasetId)?.name ?? "logs"}`,
        product_id: "uploaded-logs",
        scenario_ids: ["record"],
        fidelity_mode: "vendor_accurate",
        targets: [
          {
            id: crypto.randomUUID(),
            name:
              destination.transport_id === "azure_function_app"
                ? "Function App → DCE"
                : "DCE",
            enabled: true,
            destination,
            auth_config: auth,
            payload_format: mode === "envelope" ? "default" : "json",
            device_ids: [],
            scenario_ids: [],
            queue_limit: 10000,
          },
        ],
        replay_config: {
          dataset_id: datasetId,
          loop: false,
          timing: "fixed",
          rewrite_timestamps: rewrite,
        },
        schedule: {
          type: "finite",
          events_per_second: rate,
          event_count: checked.record_count,
        },
      });
      setSimulation(created);
      setSimulation(await startSimulation(created.id));
      setAuth((a) => ({
        ...a,
        token: undefined,
        oauth_client_secret: undefined,
      }));
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  const running = simulation?.status === "running";
  const queued =
    simulation?.targets?.reduce(
      (sum, t) => sum + Number(t.stats.queued ?? 0),
      0,
    ) ?? 0;
  return (
    <div>
      <div className="page-header">
        <h1>Upload logs</h1>
        <Link className="btn" to="/lab">
          Timed and looping replay
        </Link>
      </div>
      <p>
        Upload a file and send it once to Azure. Preview validates every record
        before any logs are sent. Files may contain up to 100 MiB.
      </p>
      {error && <ErrorAlert message={error} />}
      <form onSubmit={(e) => void send(e)}>
        <fieldset disabled={busy || running} style={{ border: 0, padding: 0 }}>
          <div className="card">
            <div className="form-row">
              <label>
                File format
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                >
                  {["ndjson", "json", "text", "csv"].map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Log file
                <input
                  type="file"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void upload(file);
                  }}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Dataset
                <select
                  aria-label="Dataset"
                  required
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                >
                  <option value="">Select a dataset</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.record_count} records)
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Payload mode
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="envelope">Custom-table envelope</option>
                  <option value="json">
                    Unchanged JSON objects (JSON / NDJSON)
                  </option>
                </select>
              </label>
            </div>
            <label>
              <input
                type="checkbox"
                checked={rewrite}
                onChange={(e) => setRewrite(e.target.checked)}
              />{" "}
              Rewrite recognized timestamps to current time
            </label>
            <div className="form-row">
              <label>
                Records per second
                <input
                  type="number"
                  min={0.1}
                  max={100}
                  step={0.1}
                  required
                  value={rate}
                  onChange={(e) => setRate(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button"
              className="btn"
              disabled={!datasetId}
              onClick={() => void preview()}
            >
              Validate and preview
            </button>
            {validation && (
              <>
                <p>
                  {validation.record_count} records validated. DCR schema
                  compatibility will be checked by Azure.
                </p>
                <pre aria-label="Ingestion preview">
                  {JSON.stringify(validation.records, null, 2)}
                </pre>
              </>
            )}
          </div>
          <div className="card">
            <div className="form-row">
              <label>
                Delivery path
                <select
                  value={destination.transport_id}
                  onChange={(e) => {
                    setDestination({
                      transport_id: e.target
                        .value as DestinationConfig["transport_id"],
                      timeout_seconds:
                        e.target.value === "azure_function_app" ? 60 : 30,
                    });
                    setAuth({ auth_method_id: "none" });
                  }}
                >
                  <option value="azure_logs_ingestion">Direct to DCE</option>
                  <option value="azure_function_app">Function App → DCE</option>
                </select>
              </label>
            </div>
            <AzureDestinationEditor
              destination={destination}
              auth={auth}
              onChange={(d, a) => {
                setDestination(d);
                setAuth(a);
              }}
              testRecord={validation?.records[0]}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!datasetId}
          >
            Upload to Azure
          </button>
        </fieldset>
      </form>
      {simulation && (
        <div className="card" aria-label="Upload progress">
          <h2>Upload progress</h2>
          <p>Status: {simulation.status}</p>
          <p>
            Generated: {simulation.runtime_stats.events_generated} · Queued:{" "}
            {queued} · Azure-accepted:{" "}
            {simulation.runtime_stats.events_successful} · Failed:{" "}
            {simulation.runtime_stats.events_failed}
          </p>
          {simulation.runtime_stats.last_error_message && (
            <p>{simulation.runtime_stats.last_error_message}</p>
          )}
          {running && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                void stopSimulation(simulation.id)
                  .then(setSimulation)
                  .catch((e) => setError(formatApiError(e)));
              }}
            >
              Stop upload
            </button>
          )}{" "}
          <Link to={`/simulations/${simulation.id}`}>
            Delivery history and saved configuration
          </Link>
          <p>
            API acceptance does not confirm table arrival. Explicitly restarting
            this run sends the file again; uncertain responses can create
            duplicates.
          </p>
        </div>
      )}
    </div>
  );
}
