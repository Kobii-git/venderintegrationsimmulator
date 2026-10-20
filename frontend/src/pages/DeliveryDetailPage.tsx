import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getSimulationEvent,
  getSimulationEventCurl,
  replaySimulationEvent,
} from "../api/simulations";
import { ConsoleTabs } from "../components/ConsoleTabs";
import { ErrorAlert } from "../components/ErrorAlert";
import { InfoAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { DeliveryBadge, HttpStatusCode } from "../components/StatusBadge";
import { JsonViewer } from "../components/JsonViewer";
import type { DeliveryAttemptResponse, EventInstanceDetail } from "../types/api";
import { copyToClipboard, formatApiError, formatDateTime } from "../utils/format";

export function DeliveryDetailPage() {
  const { id, eventId } = useParams<{ id: string; eventId: string }>();
  const [view, setView] = useState("summary");
  const [replayedEventId, setReplayedEventId] = useState<string | null>(null);
  const [event, setEvent] = useState<EventInstanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedAttemptId, setSelectedAttemptId] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !eventId) return;
    let active = true;
    setEvent(null); setSelectedAttemptId(null); setView("summary");
    setLoading(true); setError(null); setActionMessage(null); setReplayedEventId(null);
    void getSimulationEvent(id, eventId)
      .then((loaded) => {
        if (!active) return;
        setEvent(loaded);
        setSelectedAttemptId(loaded.delivery_attempts.at(-1)?.id ?? null);
      })
      .catch((err) => { if (active) setError(formatApiError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, eventId]);

  const handleCopyCurl = async () => {
    if (!id || !eventId) return;
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await getSimulationEventCurl(id, eventId, selectedAttemptId ?? undefined);
      await copyToClipboard(result.command);
      setActionMessage(
        `cURL for attempt ${result.attempt_id} copied (secrets redacted${
          result.exact ? "" : "; legacy evidence is approximate"
        })`,
      );
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleReplay = async (mode: "exact" | "regenerate") => {
    if (!id || !eventId) return;
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await replaySimulationEvent(id, eventId, { mode });
      const label = mode === "exact" ? "Exact payload replayed" : "Scenario regenerated and sent";
      setActionMessage(
        `${label} — new event ${result.correlation_id} (HTTP ${result.response_status_code ?? "—"})`,
      );
      setReplayedEventId(result.new_event_id);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingState label="Loading delivery details…" />;
  if (error && !event) return <ErrorAlert message={error} />;
  if (!event) return <ErrorAlert message="Event not found" />;

  const attempt: DeliveryAttemptResponse | undefined =
    event.delivery_attempts.find((item) => item.id === selectedAttemptId) ??
    event.delivery_attempts.at(-1);

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Delivery inspection</p><h1>Delivery Detail</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {formatDateTime(event.generated_at)} · <DeliveryBadge success={attempt?.success ?? null} />
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" disabled={busy || !attempt} onClick={() => void handleCopyCurl()}>
            Copy as cURL
          </button>
          <details className="action-menu monitor-tools"><summary>Replay options</summary><div className="action-menu-panel">
          <span className="menu-hint">Both actions send events using the current destination and credentials.</span>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void handleReplay("exact")}
            title="Resend the exact stored payload using current auth configuration"
          >
            Replay exact payload
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void handleReplay("regenerate")}
            title="Generate a fresh event from the same scenario"
          >
            Regenerate scenario
          </button>
          </div></details>
          <Link to={`/simulations/${id}?view=activity`} className="btn">
            Back to simulation
          </Link>
        </div>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {actionMessage ? <InfoAlert message={actionMessage} /> : null}
      {replayedEventId && <p><Link className="btn btn-primary" to={`/simulations/${id}/events/${replayedEventId}`}>Open replayed delivery</Link></p>}
      {attempt && <div className={`delivery-outcome ${attempt.success ? "is-success" : "is-failed"}`} role={attempt.success ? "status" : "alert"}>
        <h2>{attempt.success ? "Delivery accepted" : "Delivery attempt failed"}</h2>
        <p>{attempt.error_explanation ?? attempt.error_message ?? attempt.delivery_note ?? (attempt.success ? "The transport accepted this attempt. Confirm receipt and parsing in the destination." : "Inspect the request and response evidence below to identify the failure.")}</p>
      </div>}

      {attempt?.delivery_confirmation ? (
        <InfoAlert message={`${attempt.delivery_confirmation}: ${attempt.delivery_note ?? "Inspect the collector to confirm receipt."}`} />
      ) : null}
      <div className="card">
        <h2 style={{ fontSize: "1rem" }}>Delivery attempts</h2>
        {event.delivery_attempts.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Collector</th>
                  <th>Attempt</th>
                  <th>Started</th>
                  <th>Status</th>
                  <th>Latency</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {event.delivery_attempts.map((item) => (
                  <tr key={item.id} className={!item.success ? "delivery-row-failed" : undefined}>
                    <td>{item.target_id ?? "Primary"}</td>
                    <td>#{item.attempt_number}</td>
                    <td>{formatDateTime(item.started_at)}</td>
                    <td><DeliveryBadge success={item.success} /> {item.response_status_code != null && <HttpStatusCode code={item.response_status_code} />}</td>
                    <td>{item.latency_ms == null ? "—" : `${item.latency_ms} ms`}</td>
                    <td>
                      <button
                        type="button"
                        className={item.id === attempt?.id ? "btn btn-primary btn-sm" : "btn btn-sm"}
                        aria-pressed={item.id === attempt?.id}
                        onClick={() => setSelectedAttemptId(item.id)}
                      >
                        {item.id === attempt?.id ? "Selected" : "Select"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)" }}>No delivery attempts recorded.</p>
        )}
      </div>

      <ConsoleTabs id="delivery" label="Delivery evidence" value={view} onChange={setView} tabs={[
        { id: "summary", label: "Summary" }, { id: "exchange", label: "Request & response" }, { id: "payload", label: "Event payload" },
      ]} />
      <section role="tabpanel" id="delivery-panel-summary" aria-labelledby="delivery-tab-summary" hidden={view !== "summary"}>
      <div className="card">
        <dl className="detail-grid">
          <dt>Simulator event ID</dt>
          <dd>
            <code>{event.correlation_id}</code>{" "}
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => { void copyToClipboard(event.correlation_id).then(() => setActionMessage("Correlation ID copied.")).catch(() => setError("Clipboard unavailable. Select the correlation ID to copy it manually.")); }}
            >
              Copy
            </button>
          </dd>
          <dt>Payload source</dt>
          <dd>{event.payload_source.replace(/_/g, " ")}</dd>
          {event.replayed_from_event_id ? (
            <>
              <dt>Replayed from</dt>
              <dd>
                <Link to={`/simulations/${id}/events/${event.replayed_from_event_id}`}>
                  {event.replayed_from_event_id}
                </Link>
              </dd>
            </>
          ) : null}
          <dt>Scenario</dt>
          <dd>{event.scenario_id}</dd>
          <dt>Product</dt>
          <dd>{event.product_id}</dd>
          <dt>Fidelity</dt>
          <dd>{event.fidelity_mode}</dd>
          {attempt ? (
            <>
              <dt>Generated</dt>
              <dd>{formatDateTime(event.generated_at)}</dd>
              <dt>Request sent</dt>
              <dd>{formatDateTime(attempt.started_at)}</dd>
              <dt>Completed</dt>
              <dd>{attempt.completed_at ? formatDateTime(attempt.completed_at) : "—"}</dd>
              <dt>Destination</dt>
              <dd style={{ fontFamily: "var(--mono)", fontSize: "0.8125rem" }}>
                {attempt.request_url_redacted ?? attempt.destination_summary}
              </dd>
              <dt>Method</dt>
              <dd>{attempt.request_method}</dd>
              <dt>HTTP status</dt>
              <dd>
                <HttpStatusCode code={attempt.response_status_code} />
              </dd>
              <dt>Latency</dt>
              <dd>{attempt.latency_ms != null ? `${attempt.latency_ms} ms` : "—"}</dd>
              <dt>Attempt</dt>
              <dd>#{attempt.attempt_number}</dd>
              <dt>Error category</dt>
              <dd>{attempt.error_category ?? "—"}</dd>
              {attempt.error_explanation ? (
                <>
                  <dt>Explanation</dt>
                  <dd>{attempt.error_explanation}</dd>
                </>
              ) : null}
              {attempt.error_message ? (
                <>
                  <dt>Error</dt>
                  <dd style={{ color: "var(--danger)" }}>{attempt.error_message}</dd>
                </>
              ) : null}
            </>
          ) : null}
        </dl>
      </div>

      </section>
      <section role="tabpanel" id="delivery-panel-exchange" aria-labelledby="delivery-tab-exchange" hidden={view !== "exchange"}>
      {attempt ? (
        <div className="evidence-grid">
          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Request headers (redacted)</h2>
            <JsonViewer data={attempt.request_headers_redacted} />
          </div>

          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Query parameters (redacted)</h2>
            <JsonViewer data={attempt.request_query_params_redacted} />
          </div>

          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Request body</h2>
            {attempt.request_body ? (
              <pre className="json-viewer">{attempt.request_body}</pre>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No body</p>
            )}
          </div>

          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Response headers (redacted)</h2>
            <JsonViewer data={attempt.response_headers_redacted} />
          </div>

          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Response body</h2>
            {attempt.response_body ? (
              <pre className="json-viewer">{attempt.response_body}</pre>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No response body</p>
            )}
          </div>
        </div>
      ) : null}

      </section>
      <section role="tabpanel" id="delivery-panel-payload" aria-labelledby="delivery-tab-payload" hidden={view !== "payload"}>
      <div className="card">
        <h2 style={{ fontSize: "1rem" }}>Event payload</h2>
        <JsonViewer data={event.payload} />
      </div>
      </section>
    </div>
  );
}
