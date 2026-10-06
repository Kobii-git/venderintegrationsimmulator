import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getSimulation, sendSimulationEvent } from "../api/simulations";
import { previewScenario } from "../api/products";
import { ErrorAlert } from "../components/ErrorAlert";
import { InfoAlert } from "../components/ErrorAlert";
import { JsonEditor, JsonViewer } from "../components/JsonViewer";
import { LoadingState } from "../components/LoadingState";
import type { ScenarioPreviewResponse, SimulationResponse } from "../types/api";
import { formatApiError } from "../utils/format";

export function EventPreviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [preview, setPreview] = useState<ScenarioPreviewResponse | null>(null);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [payloadJson, setPayloadJson] = useState("");
  const [useOverride, setUseOverride] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const latestPreviewRequest = useRef(0);

  const loadSimulation = useCallback(async () => {
    if (!id) return;
    const sim = await getSimulation(id);
    setSimulation(sim);
    setSelectedScenario(sim.scenario_ids[0] ?? sim.scenario_id);
  }, [id]);

  const generatePreview = useCallback(async () => {
    if (!simulation || !selectedScenario) return;
    const requestId = latestPreviewRequest.current + 1;
    latestPreviewRequest.current = requestId;
    setGenerating(true);
    setError(null);
    setSendResult(null);
    setPreview(null);
    setPayloadJson("");
    setUseOverride(false);
    setJsonError(null);
    try {
      const result = await previewScenario(simulation.product_id, selectedScenario, {
        fidelity_mode: simulation.fidelity_mode as never,
        scenario_overrides: simulation.scenario_overrides[selectedScenario] ?? {},
      });
      if (requestId !== latestPreviewRequest.current) return;
      setPreview(result);
      setPayloadJson(JSON.stringify(result.payload, null, 2));
    } catch (err) {
      if (requestId !== latestPreviewRequest.current) return;
      setError(formatApiError(err));
    } finally {
      if (requestId === latestPreviewRequest.current) {
        setGenerating(false);
      }
    }
  }, [simulation, selectedScenario]);

  useEffect(() => {
    void loadSimulation()
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, [loadSimulation]);

  useEffect(() => {
    if (simulation && selectedScenario) {
      void generatePreview();
    }
    return () => {
      latestPreviewRequest.current += 1;
    };
  }, [simulation, selectedScenario, generatePreview]);

  const handleScenarioChange = (scenarioId: string) => {
    latestPreviewRequest.current += 1;
    setSelectedScenario(scenarioId);
    setPreview(null);
    setPayloadJson("");
    setUseOverride(false);
    setJsonError(null);
    setError(null);
    setSendResult(null);
    setGenerating(true);
  };

  const handleSend = async () => {
    if (
      !simulation ||
      !selectedScenario ||
      !id ||
      generating ||
      preview?.scenario_id !== selectedScenario
    ) {
      return;
    }

    let payloadOverride: Record<string, unknown>;
    try {
      payloadOverride = JSON.parse(payloadJson) as Record<string, unknown>;
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON — fix before sending");
      return;
    }

    setSending(true);
    setError(null);
    setSendResult(null);
    try {
      const result = await sendSimulationEvent(id, {
        payload_override: payloadOverride,
        scenario_id: selectedScenario,
        preview_correlation_id: preview?.correlation_id,
        payload_edited: useOverride,
      });
      setSendResult(
        result.delivery_success
          ? `Delivered previewed ${selectedScenario} payload — HTTP ${result.response_status_code} (${result.latency_ms} ms)`
          : `Delivery failed — ${result.error_message ?? "unknown error"}`,
      );
      setTimeout(() => navigate(`/simulations/${id}`), 1200);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSending(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!simulation) return <ErrorAlert message="Simulation not found" />;

  const activePreview = preview?.scenario_id === selectedScenario ? preview : null;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Event Preview</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {simulation.name} · fidelity: {simulation.fidelity_mode}
          </p>
        </div>
        <Link to={`/simulations/${id}`} className="btn">
          Back to live view
        </Link>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {sendResult ? <InfoAlert message={sendResult} /> : null}

      <div className="card">
        <div className="grid-2" style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <label htmlFor="preview-scenario">Scenario</label>
            <select
              id="preview-scenario"
              value={selectedScenario}
              onChange={(e) => handleScenarioChange(e.target.value)}
            >
              {simulation.scenario_ids.map((sid) => (
                <option key={sid} value={sid}>
                  {sid}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="preview-correlation-id">Correlation ID</label>
            <input
              id="preview-correlation-id"
              readOnly
              value={activePreview?.correlation_id ?? "—"}
              style={{ fontFamily: "var(--mono)" }}
            />
          </div>
        </div>

        <div className="page-actions" style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            className="btn"
            disabled={generating}
            onClick={() => void generatePreview()}
          >
            {generating ? "Generating…" : "Generate another example"}
          </button>
          <label className="checkbox-item">
            <input
              type="checkbox"
              checked={useOverride}
              disabled={generating || !activePreview}
              onChange={(e) => setUseOverride(e.target.checked)}
            />
            Edit raw JSON for one-off send
          </label>
        </div>

        {useOverride && activePreview ? (
          <JsonEditor value={payloadJson} onChange={setPayloadJson} error={jsonError} />
        ) : activePreview ? (
          <JsonViewer data={activePreview.payload} label="Generated payload" />
        ) : null}

        <div className="page-actions" style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={sending || generating || !activePreview}
            onClick={() => void handleSend()}
          >
            {sending ? "Sending…" : "Send event"}
          </button>
        </div>

        <p className="form-hint" style={{ marginTop: "0.75rem" }}>
          Send transmits exactly the displayed payload for the selected scenario using the
          simulation&apos;s saved destination and credentials. Generate another example to regenerate
          it; editing marks the event as manual_override in simulator metadata.
        </p>
      </div>
    </div>
  );
}
