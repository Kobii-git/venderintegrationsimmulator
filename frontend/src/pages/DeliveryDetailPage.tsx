import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  getSimulationEvent,
  getSimulationEventCurl,
  replaySimulationEvent,
} from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { InfoAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { DeliveryBadge, HttpStatusCode } from "../components/StatusBadge";
import { JsonViewer } from "../components/JsonViewer";
import type { DeliveryAttemptResponse, EventInstanceDetail } from "../types/api";
import { copyToClipboard, formatApiError, formatDateTime } from "../utils/format";

export function DeliveryDetailPage() {
  const { id, eventId } = useParams<{ id: string; eventId: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EventInstanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedAttemptId, setSelectedAttemptId] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !eventId) return;
    void getSimulationEvent(id, eventId)
      .then((loaded) => {
        setEvent(loaded);
        setSelectedAttemptId(loaded.delivery_attempts.at(-1)?.id ?? null);
      })
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
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
      setTimeout(() => navigate(`/simulations/${id}/events/${result.new_event_id}`), 1200);
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
          <h1>Delivery Detail</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {formatDateTime(event.generated_at)} · <DeliveryBadge success={attempt?.success ?? null} />
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" disabled={busy || !attempt} onClick={() => void handleCopyCurl()}>
            Copy as cURL
          </button>
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
          <Link to={`/simulations/${id}`} className="btn">
            Back to simulation
          </Link>
        </div>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {actionMessage ? <InfoAlert message={actionMessage} /> : null}

      {attempt?.delivery_confirmation ? (
        <InfoAlert message={`${attempt.delivery_confirmation}: ${attempt.delivery_note ?? "Inspect the collector to confirm receipt."}`} />
      ) : null}
      <div className="card">
        <h2 style={{ fontSize: "1rem" }}>Delivery attempts</h2>
        {event.delivery_attempts.length ? (
          <div className="table-wrap">
            <table>
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
                    <td><HttpStatusCode code={item.response_status_code} /></td>
                    <td>{item.latency_ms == null ? "—" : `${item.latency_ms} ms`}</td>
                    <td>
                      <button
                        type="button"
                        className={item.id === attempt?.id ? "btn btn-primary btn-sm" : "btn btn-sm"}
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

      <div className="card">
        <dl className="detail-grid">
          <dt>Simulator event ID</dt>
          <dd>
            <code>{event.correlation_id}</code>{" "}
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => void copyToClipboard(event.correlation_id)}
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

      {attempt ? (
        <>
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
        </>
      ) : null}

      <div className="card">
        <h2 style={{ fontSize: "1rem" }}>Event payload</h2>
        <JsonViewer data={event.payload} />
      </div>
    </div>
  );
}
