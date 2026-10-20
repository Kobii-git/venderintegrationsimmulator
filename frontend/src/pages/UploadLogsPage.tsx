import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, request } from "../api/client";
import { createSimulation, getSimulation, startSimulation, stopSimulation } from "../api/simulations";
import { AzureDestinationEditor } from "../components/AzureDestinationEditor";
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { WorkflowSteps } from "../components/WorkflowSteps";
import { JsonViewer } from "../components/JsonViewer";
import { StatusBadge } from "../components/StatusBadge";
import type { AuthConfigInput, Dataset, DestinationConfig, SimulationResponse } from "../types/api";
import { endpointLabel } from "../utils/endpoint";
import { formatApiError } from "../utils/format";
import { createUuid } from "../utils/uuid";

type Validation = { record_count: number; records: Record<string, unknown>[]; payload_mode: string; schema_verified: boolean };

export function UploadLogsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [format, setFormat] = useState("ndjson");
  const [mode, setMode] = useState("envelope");
  const [rewrite, setRewrite] = useState(false);
  const [rate, setRate] = useState(10);
  const [destination, setDestination] = useState<DestinationConfig>({ transport_id: "azure_logs_ingestion", timeout_seconds: 30 });
  const [auth, setAuth] = useState<AuthConfigInput>({ auth_method_id: "none" });
  const [validation, setValidation] = useState<Validation | null>(null);
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [started, setStarted] = useState(false);
  const sending = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const steps = ["Upload & validate", "Destination", "Review & send", "Progress"];
  const selectedDataset = datasets.find((item) => item.id === datasetId);

  useEffect(() => {
    let active = true;
    void get<Dataset[]>("/datasets").then((loaded) => {
      if (active) setDatasets((current) => [...current, ...loaded.filter((item) => !current.some((existing) => existing.id === item.id))]);
    }).catch((err) => { if (active) setError(formatApiError(err)); });
    return () => { active = false; };
  }, []);
  useEffect(() => { setValidation(null); }, [datasetId, mode, rewrite]);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    document.documentElement.scrollTo?.({ top: 0, behavior: "instant" });
  }, [step]);
  const queued = simulation?.targets?.reduce((sum, target) => sum + Number(target.stats.queued ?? 0), 0) ?? 0;
  const running = simulation?.status === "running";
  const inFlight = running || queued > 0;
  useEffect(() => {
    if (!simulation || !inFlight) return;
    let active = true;
    const timer = window.setInterval(() => {
      void getSimulation(simulation.id).then((value) => { if (active) setSimulation(value); })
        .catch((err) => { if (active) setError(formatApiError(err)); });
    }, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [simulation, inFlight]);

  const upload = async (file: File) => {
    setBusy(true); setError(null); setDatasetId(""); setValidation(null);
    try {
      const dataset = await request<Dataset>(`/datasets?name=${encodeURIComponent(file.name)}&format=${format}`, {
        method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" },
      });
      setDatasets((items) => [dataset, ...items]); setDatasetId(dataset.id);
    } catch (err) { setError(formatApiError(err)); }
    finally { setBusy(false); }
  };
  const validate = () => post<Validation>(`/datasets/${datasetId}/validate-ingestion`, { payload_mode: mode, rewrite_timestamps: rewrite });
  const preview = async () => {
    setBusy(true); setError(null); setValidation(null);
    try { setValidation(await validate()); }
    catch (err) { setError(formatApiError(err)); }
    finally { setBusy(false); }
  };
  const back = (index: number) => { setError(null); setStep(index); };
  const startSaved = async (saved: SimulationResponse) => {
    const current = await getSimulation(saved.id);
    if (current.status === "running" || current.runtime_stats.events_generated > 0) {
      setSimulation(current); setStarted(true); return;
    }
    setSimulation(await startSimulation(saved.id)); setStarted(true);
    setAuth((value) => ({ ...value, token: undefined, oauth_client_secret: undefined }));
  };
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || sending.current) return;
    if (step === 0) {
      if (!validation) { setError("Validate and preview this dataset before continuing."); return; }
      setError(null); setStep(1); return;
    }
    if (step === 1) { setError(null); setStep(2); return; }
    if (step !== 2 || simulation || !validation) return;
    sending.current = true; setBusy(true); setError(null);
    try {
      const checked = await validate();
      setValidation(checked);
      const created = await createSimulation({
        name: `Upload: ${selectedDataset?.name ?? "logs"}`, product_id: "uploaded-logs", scenario_ids: ["record"], fidelity_mode: "vendor_accurate",
        targets: [{ id: createUuid(), name: destination.transport_id === "azure_function_app" ? "Function App → DCE" : "DCE",
          enabled: true, destination, auth_config: auth, payload_format: mode === "envelope" ? "default" : "json", device_ids: [], scenario_ids: [], queue_limit: 10000 }],
        replay_config: { dataset_id: datasetId, loop: false, timing: "fixed", rewrite_timestamps: rewrite },
        schedule: { type: "finite", events_per_second: rate, event_count: checked.record_count },
      });
      setSimulation(created); setStep(3);
      // Keep the saved run if Start fails, so retry never creates a second simulation.
      setSimulation(await startSimulation(created.id)); setStarted(true);
      setAuth((value) => ({ ...value, token: undefined, oauth_client_secret: undefined }));
    } catch (err) { setError(formatApiError(err)); }
    finally { sending.current = false; setBusy(false); }
  };

  return <div>
    <div className="page-header"><div><p className="eyebrow">Log tools</p><h1>Upload logs</h1>
      <p className="page-description">Validate a dataset, review its destination, and send it once to Azure.</p></div>
      <Link className="btn" to="/lab">Timed and looping replay<Icon name="arrow" /></Link></div>
    <WorkflowSteps steps={steps} current={step} onBack={back} disabled={busy} />
    {error && <ErrorAlert message={error} />}
    <form ref={formRef} onSubmit={(event) => void send(event)}>
      <div className="card setup-panel">
        <div className="setup-panel-header"><p className="eyebrow">Step {step + 1} of 4</p><h2 ref={heading} tabIndex={-1}>{steps[step]}</h2>
          <p className="page-description">{["Choose an existing dataset or upload a UTF-8 file, up to 100 MiB.", "Configure Azure ingestion or a Function App relay. Authentication checks send no records.", "The next action sends records. Review the file, payload, and destination first.", "Track accepted, failed, and queued records until delivery drains."][step]}</p></div>
        <fieldset className="setup-fields" disabled={busy || step !== 0} hidden={step !== 0}>
          <legend className="sr-only">Upload and validate</legend><div className="form-grid">
            <div className="grid-2"><div className="form-row"><label htmlFor="upload-format">File format</label><select id="upload-format" value={format} onChange={(event) => setFormat(event.target.value)}>
              {["ndjson", "json", "text", "csv"].map((item) => <option key={item}>{item}</option>)}</select><span className="form-hint">Used for the next file upload.</span></div>
              <div className="form-row"><label htmlFor="upload-dataset">Dataset</label><select id="upload-dataset" required value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
                <option value="">Select a dataset</option>{datasets.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.record_count} records)</option>)}</select></div></div>
            <div className="file-picker"><Icon name="upload" /><div className="form-row"><label htmlFor="upload-file">Log file</label>
              <input id="upload-file" type="file" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void upload(file); }} />
              <span className="form-hint">Files are stored as datasets for preview and replay. Uploading a file does not send it to Azure.</span></div></div>
            <div className="grid-2"><div className="form-row"><label htmlFor="upload-mode">Payload mode</label><select id="upload-mode" value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="envelope">Custom-table envelope</option><option value="json">Unchanged JSON objects (JSON / NDJSON)</option></select></div>
              <div className="form-row"><label htmlFor="upload-rate">Records per second</label><input id="upload-rate" type="number" min={0.1} max={100} step={0.1} required value={rate} onChange={(event) => setRate(Number(event.target.value))} /></div></div>
            <label className="checkbox-item"><input type="checkbox" checked={rewrite} onChange={(event) => setRewrite(event.target.checked)} />Rewrite recognized timestamps to current time</label>
            <div className="page-actions"><button type="button" className="btn" disabled={!datasetId || busy} onClick={() => void preview()}>{busy ? "Working…" : "Validate and preview"}</button></div>
            {validation && <div className="validation-result"><p role="status"><strong>{validation.record_count.toLocaleString()} records validated.</strong> DCR schema compatibility will be checked by Azure.</p>
              <JsonViewer data={validation.records} label="Ingestion preview" /></div>}
          </div>
        </fieldset>
        <fieldset className="setup-fields" disabled={busy || step !== 1} hidden={step !== 1}>
          <legend className="sr-only">Upload destination</legend><div className="form-grid">
            <div className="form-row"><label htmlFor="upload-path">Delivery path</label><select id="upload-path" value={destination.transport_id} onChange={(event) => {
              setDestination({ transport_id: event.target.value as DestinationConfig["transport_id"], timeout_seconds: event.target.value === "azure_function_app" ? 60 : 30 }); setAuth({ auth_method_id: "none" });
            }}><option value="azure_logs_ingestion">Direct to DCE</option><option value="azure_function_app">Function App → DCE</option></select></div>
            <AzureDestinationEditor destination={destination} auth={auth} onChange={(value, credentials) => { setDestination(value); setAuth(credentials); }} testRecord={validation?.records[0]} />
          </div>
        </fieldset>
        {step === 2 && validation && <div className="review-grid">
          <section><h3>Dataset & payload</h3><dl className="review-values"><dt>File</dt><dd>{selectedDataset?.name}</dd><dt>Records</dt><dd>{validation.record_count.toLocaleString()}</dd>
            <dt>Payload</dt><dd>{mode === "json" ? "Unchanged JSON objects" : "Custom-table envelope"}</dd><dt>Timestamps</dt><dd>{rewrite ? "Rewrite recognized timestamps" : "Keep original timestamps"}</dd><dt>Pacing</dt><dd>{rate} records per second · one pass</dd></dl></section>
          <section className="review-section"><h3>Destination</h3><dl className="review-values"><dt>Path</dt><dd>{destination.transport_id === "azure_function_app" ? "Function App → DCE" : "Direct to DCE"}</dd>
            <dt>Endpoint</dt><dd>{endpointLabel(destination.url ?? destination.endpoint)}</dd>{destination.stream && <><dt>Stream</dt><dd>{destination.stream}</dd></>}
            <dt>Credentials</dt><dd>Hidden from this summary. Secrets are encrypted when saved.</dd></dl></section>
          <div className="alert alert-info">API acceptance does not confirm table arrival. Repeating an upload or retrying an uncertain result may create duplicates.</div>
        </div>}
        {step === 3 && simulation && <section aria-label="Upload progress" className="upload-progress">
          <div className="section-heading"><span className="empty-mark"><Icon name="upload" /></span><div><h3>Upload progress</h3><p>Status: <StatusBadge status={simulation.status} /></p></div></div>
          <div className="metric-grid"><div className="metric"><span>Generated</span><strong>{simulation.runtime_stats.events_generated}</strong></div><div className="metric"><span>Queued</span><strong>{queued}</strong></div>
            <div className="metric"><span>Azure-accepted</span><strong>{simulation.runtime_stats.events_successful}</strong></div><div className="metric"><span>Failed</span><strong>{simulation.runtime_stats.events_failed}</strong></div></div>
          <p className="form-hint">{inFlight ? "Delivery is still in progress. Queued records may continue draining after Stop." : "No records are currently queued. Inspect delivery history to review the result."}</p>
          {simulation.runtime_stats.last_error_message && <ErrorAlert message={simulation.runtime_stats.last_error_message} />}
          <div className="page-actions">
            {running && <button type="button" className="btn" disabled={busy} onClick={() => { setBusy(true); void stopSimulation(simulation.id).then(setSimulation).catch((err) => setError(formatApiError(err))).finally(() => setBusy(false)); }}>Stop upload</button>}
            {!started && !inFlight && <button type="button" className="btn" disabled={busy} onClick={() => { setBusy(true); setError(null); void startSaved(simulation).catch((err) => setError(formatApiError(err))).finally(() => setBusy(false)); }}>Start saved upload</button>}
            <Link className="btn btn-primary" to={`/simulations/${simulation.id}`}>Delivery history and saved configuration</Link>
            <button type="button" className="btn" disabled={inFlight || busy} onClick={() => { setSimulation(null); setStarted(false); setValidation(null); setAuth({ auth_method_id: "none" }); setStep(0); setError(null); }}>Start another upload</button>
          </div><p className="form-hint">API acceptance does not confirm table arrival. Restarting a saved run sends the file again; uncertain responses can create duplicates.</p>
        </section>}
      </div>
      {step < 3 && <div className="setup-footer"><div>{step > 0 && <button type="button" className="btn" disabled={busy} onClick={() => back(step - 1)}>Back</button>}</div>
        <div className="setup-footer-next"><span className="form-hint">{step === 2 ? "This sends the validated file to the reviewed destination." : "Nothing is sent to Azure by continuing."}</span>
          <button type="submit" className="btn btn-primary" disabled={busy || (step === 0 && !validation)}>{busy ? "Working…" : step === 2 ? "Upload to Azure" : "Continue"}<Icon name={step === 2 ? "upload" : "arrow"} /></button></div></div>}
    </form>
  </div>;
}
