import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getSimulation, sendSimulationEvent } from "../api/simulations";
import { previewScenario } from "../api/products";
import { ErrorAlert, InfoAlert, WarningAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { JsonEditor, JsonViewer } from "../components/JsonViewer";
import { LoadingState } from "../components/LoadingState";
import type { FidelityMode, ScenarioPreviewResponse, SimulationResponse, SimulationSendResponse } from "../types/api";
import { endpointLabel } from "../utils/endpoint";
import { formatApiError } from "../utils/format";

export function EventPreviewPage() {
  const { id } = useParams<{ id: string }>();
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [preview, setPreview] = useState<ScenarioPreviewResponse | null>(null);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [payloadJson, setPayloadJson] = useState("");
  const [useOverride, setUseOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<SimulationSendResponse | null>(null);
  const latestPreviewRequest = useRef(0);
  const sendPending = useRef(false);

  useEffect(() => {
    let active = true;
    setLoading(true); setSimulation(null); setPreview(null); setSendResult(null); setError(null);
    if (id) void getSimulation(id).then((sim) => {
      if (!active) return;
      setSimulation(sim); setSelectedScenario(sim.scenario_ids[0] ?? sim.scenario_id);
    }).catch((err) => { if (active) setError(formatApiError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; latestPreviewRequest.current += 1; };
  }, [id, retry]);

  const generatePreview = useCallback(async () => {
    if (!simulation || !selectedScenario || sendPending.current) return;
    const requestId = ++latestPreviewRequest.current;
    setGenerating(true); setError(null); setSendResult(null); setPreview(null); setPayloadJson(""); setUseOverride(false);
    try {
      const result = await previewScenario(simulation.product_id, selectedScenario, {
        fidelity_mode: simulation.fidelity_mode as FidelityMode,
        scenario_overrides: simulation.scenario_overrides[selectedScenario] ?? {},
      });
      if (requestId !== latestPreviewRequest.current) return;
      setPreview(result); setPayloadJson(JSON.stringify(result.payload, null, 2));
    } catch (err) { if (requestId === latestPreviewRequest.current) setError(formatApiError(err)); }
    finally { if (requestId === latestPreviewRequest.current) setGenerating(false); }
  }, [simulation, selectedScenario]);

  useEffect(() => {
    void generatePreview();
    return () => { latestPreviewRequest.current += 1; };
  }, [generatePreview]);

  const activePreview = preview?.scenario_id === selectedScenario ? preview : null;
  let editedPayload: Record<string, unknown> | null = null;
  let jsonError: string | null = null;
  if (useOverride) {
    try {
      const parsed: unknown = JSON.parse(payloadJson);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) jsonError = "Use a JSON object, rather than an array or a single value.";
      else editedPayload = parsed as Record<string, unknown>;
    } catch { jsonError = "Invalid JSON — fix before sending."; }
  }
  const blocked = simulation?.simulation_mode === "pull_api" ? "Pull API simulations are polled by a collector. Open Connection in the live view to find the mock API routes."
    : simulation?.missing_secrets.length ? `Add these credentials in Edit before sending: ${simulation.missing_secrets.join(", ")}` : null;
  const handleSend = async () => {
    if (!id || !activePreview || !simulation || generating || blocked || jsonError || sendPending.current) return;
    const version = latestPreviewRequest.current;
    const payload = useOverride ? editedPayload : activePreview.payload;
    if (!payload) return;
    sendPending.current = true; setSending(true); setError(null); setSendResult(null);
    try {
      const result = await sendSimulationEvent(id, {
        payload_override: payload, scenario_id: selectedScenario,
        preview_correlation_id: activePreview.correlation_id, payload_edited: useOverride,
      });
      if (version === latestPreviewRequest.current) setSendResult(result);
    } catch (err) { if (version === latestPreviewRequest.current) setError(formatApiError(err)); }
    finally { sendPending.current = false; if (version === latestPreviewRequest.current) setSending(false); }
  };

  if (loading) return <LoadingState label="Loading event preview…" />;
  if (!simulation) return <div><div className="page-header"><h1>Event Preview</h1></div><ErrorAlert message={error ?? "Simulation not found"} /><div className="page-actions"><Link className="btn" to={`/simulations/${id}`}>Back to live view</Link><button type="button" className="btn" onClick={() => setRetry((value) => value + 1)}>Try again</button></div></div>;
  const destinations = simulation.targets?.filter((target) => target.enabled).map((target) => ({ name: target.name, destination: target.destination }))
    ?? [{ name: "Primary", destination: simulation.destination }];

  return <div>
    <div className="page-header"><div><p className="eyebrow">Test workspace</p><h1>Event Preview</h1>
      <p className="page-description">Inspect one event, make optional edits, and send it when you are ready.</p></div>
      <Link to={`/simulations/${id}`} className="btn">Back to live view</Link></div>
    <div className="tool-notice"><Icon name="code" /><span>Generating a preview sends nothing. Send event delivers the displayed payload using the saved configuration.</span></div>
    {error && <ErrorAlert message={error} />}
    {blocked && <WarningAlert message={blocked} />}
    {sendResult && <div className="preview-send-result">
      {sendResult.delivery_success ? <InfoAlert message={`Delivered previewed ${sendResult.scenario_id} payload${sendResult.response_status_code != null ? ` — HTTP ${sendResult.response_status_code}` : " — transport accepted"}${sendResult.latency_ms != null ? ` (${sendResult.latency_ms} ms)` : ""}`} />
        : <ErrorAlert message={`Delivery failed — ${sendResult.error_message ?? "Inspect the recorded attempt for details."}`} />}
      <Link className="btn" to={`/simulations/${id}/events/${sendResult.event_id}`}>Inspect this delivery<Icon name="arrow" /></Link>
      <p className="form-hint">The preview stays open for comparison. Sending again creates another delivery. Acceptance does not confirm downstream parsing.</p>
    </div>}
    <div className="preview-workspace">
      <aside className="card preview-controls" aria-label="Preview configuration">
        <div className="section-heading"><span className="section-number">1</span><div><h2>Choose an event</h2><p>{simulation.name}</p></div></div>
        <div className="form-row"><label htmlFor="preview-scenario">Scenario</label><select id="preview-scenario" value={selectedScenario} disabled={sending} onChange={(event) => {
          latestPreviewRequest.current += 1; setSelectedScenario(event.target.value); setPreview(null); setUseOverride(false); setSendResult(null);
        }}>{simulation.scenario_ids.map((scenario) => <option key={scenario}>{scenario}</option>)}</select></div>
        <p className="form-hint">{activePreview?.scenario_description}</p>
        <button type="button" className="btn" disabled={generating || sending} onClick={() => void generatePreview()}>{generating ? "Generating…" : "Generate another example"}</button>
        <p className="form-hint">Changing scenario or generating again replaces any unsaved JSON edits.</p>
        <dl className="summary-values"><dt>Product</dt><dd>{simulation.product_id}</dd><dt>Payload mode</dt><dd>{simulation.fidelity_mode === "vendor_accurate" ? "Vendor payload" : "Simulator diagnostics"}</dd>
          <dt>Saved destinations</dt><dd>{destinations.length ? <ul className="destination-list">{destinations.map(({ name, destination }, index) => <li key={index}><strong>{name}</strong><span>{destination.transport_id === "syslog" ? `${destination.protocol?.toUpperCase() ?? "Syslog"} · ${destination.host}:${destination.port}` : endpointLabel(destination.url ?? destination.endpoint)}</span></li>)}</ul> : "No enabled collectors"}</dd></dl>
        <Link to={`/simulations/${id}?view=connection`}>Review saved connection<Icon name="arrow" /></Link>
      </aside>
      <section className="card output-panel preview-payload" aria-label="Payload workspace" aria-busy={generating}>
        <div className="section-heading"><span className="section-number">2</span><div><h2>Inspect payload</h2><p>Send exactly what you see below.</p></div></div>
        <div className="form-row"><label htmlFor="preview-correlation-id">Correlation ID</label><input id="preview-correlation-id" readOnly value={activePreview?.correlation_id ?? "—"} className="mono-field" /></div>
        <div className="preview-edit-bar"><label className="checkbox-item"><input type="checkbox" checked={useOverride} disabled={generating || sending || !activePreview} onChange={(event) => setUseOverride(event.target.checked)} />Edit raw JSON for one-off send</label>
          {useOverride && <button type="button" className="btn btn-sm" disabled={sending} onClick={() => setPayloadJson(JSON.stringify(activePreview?.payload, null, 2))}>Reset edits</button>}</div>
        {generating ? <LoadingState label="Generating payload…" /> : activePreview ? useOverride
          ? <JsonEditor value={payloadJson} onChange={setPayloadJson} error={jsonError} disabled={sending} label="Payload JSON" />
          : <JsonViewer data={activePreview.payload} label="Generated payload" /> : <p className="inline-empty">No preview available. Generate another example to try again.</p>}
        <div className="preview-send-bar"><span className="form-hint">{useOverride ? "Your edited JSON will be recorded as a manual override." : "The generated payload will be sent without edits."}</span>
          <button type="button" className="btn btn-primary" disabled={sending || generating || !activePreview || !!blocked || !!jsonError || !destinations.length} onClick={() => void handleSend()}>{sending ? "Sending…" : sendResult ? "Send again" : "Send event"}<Icon name="arrow" /></button></div>
      </section>
    </div>
  </div>;
}
