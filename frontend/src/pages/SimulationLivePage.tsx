import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getProduct } from "../api/products";
import {
  burstSimulationEvents,
  executeSimulationAction,
  exportSimulation,
  getInboundEndpointInfo,
  getSimulation,
  listInboundRequests,
  listOAuthTokens,
  listSimulationEvents,
  sendSimulationEvent,
  startSimulation,
  stopSimulation,
} from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { WarningAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode, StatusBadge } from "../components/StatusBadge";
import { usePolling } from "../hooks/usePolling";
import type {
  EventInstanceSummary,
  InboundEndpointInfo,
  InboundRequestSummary,
  IssuedOAuthToken,
  ProductDetail,
  SimulationResponse,
  WorkflowActionResponse,
} from "../types/api";
import {
  copyToClipboard,
  formatApiError,
  formatDateTime,
  formatTime,
} from "../utils/format";

export function SimulationLivePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [events, setEvents] = useState<EventInstanceSummary[]>([]);
  const [inboundRequests, setInboundRequests] = useState<
    InboundRequestSummary[]
  >([]);
  const [oauthTokens, setOauthTokens] = useState<IssuedOAuthToken[]>([]);
  const [endpointInfo, setEndpointInfo] = useState<InboundEndpointInfo | null>(
    null,
  );
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [workflowResult, setWorkflowResult] =
    useState<WorkflowActionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filterSuccess, setFilterSuccess] = useState<"" | "true" | "false">("");
  const [filterScenario, setFilterScenario] = useState("");
  const [filterHttpStatus, setFilterHttpStatus] = useState("");
  const [filterCorrelation, setFilterCorrelation] = useState("");
  const [burstCount, setBurstCount] = useState(5);
  const [burstIntervalMs, setBurstIntervalMs] = useState(0);
  const [confirmLargeBurst, setConfirmLargeBurst] = useState(false);

  const refresh = useCallback(async () => {
    if (!id) return;
    try {
      const filters = {
        limit: 50,
        scenario_id: filterScenario || undefined,
        success: filterSuccess === "" ? undefined : filterSuccess === "true",
        http_status: filterHttpStatus ? Number(filterHttpStatus) : undefined,
        correlation_id: filterCorrelation || undefined,
      };
      const [sim, evts] = await Promise.all([
        getSimulation(id),
        listSimulationEvents(id, filters),
      ]);
      setSimulation(sim);
      setEvents(evts);
      if (sim.simulation_mode === "pull_api") {
        const [requests, endpoint, tokens] = await Promise.all([
          listInboundRequests(id, 50),
          getInboundEndpointInfo(id),
          sim.inbound_config?.auth_method_id === "oauth2_client_credentials"
            ? listOAuthTokens(id, 50)
            : Promise.resolve([]),
        ]);
        setInboundRequests(requests);
        setEndpointInfo(endpoint);
        setOauthTokens(tokens);
      } else {
        setInboundRequests([]);
        setOauthTokens([]);
        setEndpointInfo(null);
      }
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [id, filterSuccess, filterScenario, filterHttpStatus, filterCorrelation]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!simulation?.product_id) return;
    void getProduct(simulation.product_id)
      .then(setProduct)
      .catch((err) => setError(formatApiError(err)));
  }, [simulation?.product_id]);

  const isLive = simulation?.status === "running";
  usePolling(refresh, 2000, isLive);
  usePolling(refresh, 5000, !isLive && !loading);

  const runAction = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setActionError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const runWorkflowAction = async (actionId: string) => {
    setBusy(true);
    setActionError(null);
    setWorkflowResult(null);
    try {
      const result = await executeSimulationAction(id ?? "", actionId);
      setWorkflowResult(result);
      await refresh();
    } catch (err) {
      setActionError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingState label="Loading simulation…" />;
  if (!simulation || !id) return <ErrorAlert message="Simulation not found" />;

  const stats = simulation.runtime_stats;
  const faultsEnabled = simulation.fault_config?.enabled === true;
  const isPull = simulation.simulation_mode === "pull_api";
  const isOAuth =
    simulation.inbound_config?.auth_method_id === "oauth2_client_credentials";
  const inboundFaultsEnabled =
    simulation.inbound_config?.fault_config?.enabled === true;
  const workflowActions = (product?.actions ?? []).filter((action) =>
    action.supported_modes.includes(
      simulation.simulation_mode as "pull_api" | "push_webhook",
    ),
  );

  return (
    <div>
      {!isPull && simulation.targets?.length ? (
        <div className="card">
          <h2>Collector delivery</h2>
          <table>
            <thead>
              <tr>
                <th>Collector</th>
                <th>Format</th>
                <th>Accepted</th>
                <th>Failed</th>
                <th>Queued</th>
                <th>Confirmation</th>
                <th>Last error</th>
              </tr>
            </thead>
            <tbody>
              {simulation.targets.map((t) => (
                <tr key={t.id}>
                  <td>
                    {t.name} {t.enabled ? "" : "(disabled)"}
                  </td>
                  <td>{t.payload_format}</td>
                  <td>{t.stats.successful ?? 0}</td>
                  <td>{t.stats.failed ?? 0}</td>
                  <td>{t.stats.queued ?? 0}</td>
                  <td>{t.stats.confirmation ?? "—"}</td>
                  <td>{t.stats.last_error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="page-header">
        <div>
          <h1>{simulation.name}</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {simulation.product_id} · {isPull ? "pull API" : "push webhook"} ·{" "}
            <StatusBadge status={simulation.status} />{" "}
            <span className={`polling-indicator ${isLive ? "live" : ""}`}>
              {isLive ? "Live polling" : "Polling every 5s"}
            </span>
          </p>
        </div>
        <div className="page-actions">
          {simulation.status !== "running" ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={
                busy ||
                simulation.missing_secrets.length > 0 ||
                (!isPull && simulation.schedule?.type === "manual")
              }
              onClick={() => void runAction(() => startSimulation(id))}
            >
              Start
            </button>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => void runAction(() => stopSimulation(id))}
            >
              Stop
            </button>
          )}
          {!isPull ? (
            <>
              <button
                type="button"
                className="btn"
                disabled={busy || simulation.missing_secrets.length > 0}
                onClick={() => void runAction(() => sendSimulationEvent(id))}
              >
                Send one now
              </button>
              <Link to={`/lab/${id}`} className="btn">
                Collectors &amp; replay
              </Link>
              <Link to={`/simulations/${id}/preview`} className="btn">
                Preview event
              </Link>
            </>
          ) : null}
          {workflowActions.map((action) => (
            <button
              key={action.id}
              type="button"
              className="btn"
              disabled={busy || simulation.missing_secrets.length > 0}
              title={action.description ?? undefined}
              onClick={() => void runWorkflowAction(action.id)}
            >
              {action.display_name}
            </button>
          ))}
          <Link to={`/simulations/${id}/edit`} className="btn">
            Edit
          </Link>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() =>
              void runAction(async () => {
                const doc = await exportSimulation(id);
                const blob = new Blob([JSON.stringify(doc, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = `${simulation.name.replace(/\s+/g, "-").toLowerCase()}-export.json`;
                anchor.click();
                URL.revokeObjectURL(url);
              })
            }
          >
            Export config
          </button>
        </div>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {actionError ? <ErrorAlert message={actionError} /> : null}
      {workflowResult ? (
        <div
          className={
            workflowResult.delivery_success
              ? "alert alert-info"
              : "alert alert-error"
          }
        >
          {workflowResult.action_id}:{" "}
          {workflowResult.assertion_passed ? "verified" : "failed"}
          {workflowResult.response_status_code
            ? ` (HTTP ${workflowResult.response_status_code})`
            : ""}
        </div>
      ) : null}
      {stats.interrupted_on_restart ? (
        <WarningAlert message="This simulation was interrupted by a server restart and is stopped. Start it again to resume." />
      ) : null}
      {simulation.missing_secrets.length ? (
        <WarningAlert
          message={`Start/Send is blocked until these credentials are supplied: ${simulation.missing_secrets.join(", ")}`}
        />
      ) : null}
      {faultsEnabled ? (
        <WarningAlert message="Fault injection is ENABLED — events are intentionally modified for integration testing." />
      ) : null}

      {inboundFaultsEnabled ? (
        <WarningAlert message="Inbound fault injection is ENABLED — mock API responses are intentionally modified." />
      ) : null}

      <div className="stat-grid" style={{ marginBottom: "1rem" }}>
        {isPull ? (
          <>
            <div className="stat-card">
              <div className="stat-label">Inbound requests</div>
              <div className="stat-value">
                {stats.inbound_requests_total ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Successful</div>
              <div className="stat-value success">
                {stats.inbound_requests_successful ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Failed</div>
              <div className="stat-value failed">
                {stats.inbound_requests_failed ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Items returned</div>
              <div className="stat-value">
                {stats.inbound_items_returned_total ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Dataset items</div>
              <div className="stat-value">
                {stats.pull_dataset_item_count ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last request</div>
              <div className="stat-value" style={{ fontSize: "0.875rem" }}>
                {formatDateTime(stats.last_inbound_at)}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="stat-card">
              <div className="stat-label">Sent</div>
              <div className="stat-value">{stats.events_generated}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Successful</div>
              <div className="stat-value success">
                {stats.events_successful}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Failed</div>
              <div className="stat-value failed">{stats.events_failed}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last Status</div>
              <div className="stat-value">
                <HttpStatusCode code={stats.last_http_status} />
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last Latency</div>
              <div className="stat-value">
                {stats.last_latency_ms != null
                  ? `${stats.last_latency_ms} ms`
                  : "—"}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <dl className="detail-grid">
          {isPull ? (
            <>
              <dt>Mode</dt>
              <dd>Pull API (collector polls simulator)</dd>
              <dt>Auth</dt>
              <dd>{simulation.inbound_config?.auth_method_id ?? "none"}</dd>
              {isOAuth && endpointInfo?.oauth_token_url ? (
                <>
                  <dt>OAuth token URL</dt>
                  <dd className="copyable-endpoint">
                    <code>POST {endpointInfo.oauth_token_url}</code>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() =>
                        void copyToClipboard(endpointInfo.oauth_token_url ?? "")
                      }
                    >
                      Copy
                    </button>
                  </dd>
                  <dt>Token TTL</dt>
                  <dd>{endpointInfo.oauth_token_ttl_seconds ?? "—"} seconds</dd>
                </>
              ) : null}
              <dt>Mock routes</dt>
              <dd>
                {endpointInfo?.routes.map((route) => (
                  <div key={route.id} className="copyable-endpoint">
                    <code>
                      {route.methods.join(", ")} {route.url}
                    </code>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => void copyToClipboard(route.url)}
                    >
                      Copy
                    </button>
                  </div>
                )) ?? "—"}
              </dd>
              <dt>Dataset activation</dt>
              <dd>
                <code>{stats.pull_dataset_activation_id ?? "Not active"}</code>
              </dd>
              <dt>Dataset shape</dt>
              <dd>
                {simulation.inbound_config?.dataset_size ?? 100} items/route,{" "}
                {simulation.inbound_config?.item_interval_seconds ?? 60}s apart
              </dd>
              <dt>Pagination</dt>
              <dd>
                Follow the returned terminal <code>nextPageToken</code>; omit it
                when empty. Use
                <code> since=ISO-8601</code> on time-filter routes.
              </dd>
              <dt>Query hint</dt>
              <dd style={{ fontSize: "0.875rem" }}>
                Append <code>?simulation_id={id}</code> when polling if multiple
                pull simulations share this product.
              </dd>
            </>
          ) : (
            <>
              <dt>Destination</dt>
              <dd style={{ fontFamily: "var(--mono)", fontSize: "0.8125rem" }}>
                {simulation.destination?.url ?? simulation.destination?.host}
              </dd>
              <dt>Last sent</dt>
              <dd>{formatDateTime(stats.last_delivery_at)}</dd>
            </>
          )}
          <dt>Scenarios</dt>
          <dd>{simulation.scenario_ids.join(", ")}</dd>
          {!isPull ? (
            <>
              <dt>Schedule</dt>
              <dd>
                {simulation.schedule?.type}
                {simulation.schedule?.interval_seconds
                  ? ` · every ${simulation.schedule.interval_seconds}s`
                  : ""}
                {simulation.schedule?.event_count
                  ? ` · ${simulation.schedule.event_count} events`
                  : ""}
              </dd>
            </>
          ) : null}
        </dl>
      </div>

      {isPull ? (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2 style={{ fontSize: "1rem" }}>Inbound request history</h2>
          {isOAuth && oauthTokens.length > 0 ? (
            <>
              <h3 style={{ fontSize: "0.9375rem", marginTop: "1rem" }}>
                Issued tokens (metadata only)
              </h3>
              <div className="table-wrap" style={{ marginBottom: "1rem" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Record ID</th>
                      <th>Issued</th>
                      <th>Client ID</th>
                      <th>Scope</th>
                      <th>Expires</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {oauthTokens.map((token) => (
                      <tr key={token.id}>
                        <td>
                          <code>{token.id}</code>
                        </td>
                        <td>{formatTime(token.issued_at)}</td>
                        <td>{token.client_id}</td>
                        <td>{token.scope ?? "—"}</td>
                        <td>{formatTime(token.expires_at)}</td>
                        <td>
                          {token.is_expired
                            ? "expired"
                            : token.revoked
                              ? "revoked"
                              : "active"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          {inboundRequests.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              No inbound requests yet. Start the simulation and poll the mock
              API routes.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Latency</th>
                    <th>Route</th>
                    <th>Kind</th>
                    <th>Auth</th>
                    <th>Items</th>
                  </tr>
                </thead>
                <tbody>
                  {inboundRequests.map((request) => (
                    <tr
                      key={request.id}
                      className="clickable"
                      onClick={() =>
                        navigate(
                          `/simulations/${id}/inbound-requests/${request.id}`,
                        )
                      }
                    >
                      <td>{formatTime(request.received_at)}</td>
                      <td>
                        <HttpStatusCode code={request.response_status_code} />
                      </td>
                      <td>{request.latency_ms} ms</td>
                      <td>{request.route_id}</td>
                      <td>{request.request_kind ?? "api"}</td>
                      <td>
                        {request.auth_method_id} ({request.auth_result})
                      </td>
                      <td>{request.items_returned}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1rem" }}>Burst send</h2>
            <p className="form-hint" style={{ marginBottom: "0.75rem" }}>
              Send multiple events with safety limits (max 50, confirmation
              required above 20).
            </p>
            <div className="grid-2">
              <div className="form-row">
                <label htmlFor="burst-count">Event count</label>
                <input
                  id="burst-count"
                  type="number"
                  min={1}
                  max={50}
                  value={burstCount}
                  onChange={(e) => setBurstCount(Number(e.target.value))}
                />
              </div>
              <div className="form-row">
                <label htmlFor="burst-interval">
                  Interval between events (ms)
                </label>
                <input
                  id="burst-interval"
                  type="number"
                  min={0}
                  value={burstIntervalMs}
                  onChange={(e) => setBurstIntervalMs(Number(e.target.value))}
                />
              </div>
            </div>
            {burstCount > 20 ? (
              <label className="checkbox-item" style={{ marginTop: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={confirmLargeBurst}
                  onChange={(e) => setConfirmLargeBurst(e.target.checked)}
                />
                Confirm large burst ({burstCount} events)
              </label>
            ) : null}
            <div className="page-actions" style={{ marginTop: "0.75rem" }}>
              <button
                type="button"
                className="btn"
                disabled={busy || (burstCount > 20 && !confirmLargeBurst)}
                onClick={() =>
                  void runAction(() =>
                    burstSimulationEvents(id, {
                      count: burstCount,
                      interval_ms: burstIntervalMs,
                      confirm_large_run:
                        burstCount > 20 ? confirmLargeBurst : false,
                    }),
                  )
                }
              >
                Send burst
              </button>
            </div>
          </div>

          <div className="card">
            <h2 style={{ fontSize: "1rem" }}>Delivery history</h2>
            <div className="grid-2" style={{ marginBottom: "1rem" }}>
              <div className="form-row">
                <label htmlFor="filter-success">Outcome</label>
                <select
                  id="filter-success"
                  value={filterSuccess}
                  onChange={(e) =>
                    setFilterSuccess(e.target.value as "" | "true" | "false")
                  }
                >
                  <option value="">All</option>
                  <option value="true">Success</option>
                  <option value="false">Failed</option>
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="filter-scenario">Scenario</label>
                <select
                  id="filter-scenario"
                  value={filterScenario}
                  onChange={(e) => setFilterScenario(e.target.value)}
                >
                  <option value="">All</option>
                  {simulation.scenario_ids.map((sid) => (
                    <option key={sid} value={sid}>
                      {sid}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="filter-http">HTTP status</label>
                <input
                  id="filter-http"
                  type="number"
                  placeholder="e.g. 500"
                  value={filterHttpStatus}
                  onChange={(e) => setFilterHttpStatus(e.target.value)}
                />
              </div>
              <div className="form-row">
                <label htmlFor="filter-correlation">Correlation ID</label>
                <input
                  id="filter-correlation"
                  placeholder="Search simulator event ID"
                  value={filterCorrelation}
                  onChange={(e) => setFilterCorrelation(e.target.value)}
                  style={{ fontFamily: "var(--mono)" }}
                />
              </div>
            </div>

            {events.length === 0 ? (
              <p style={{ color: "var(--text-muted)" }}>
                No events match the current filters.
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Status</th>
                      <th>Latency</th>
                      <th>Scenario</th>
                      <th>Source</th>
                      <th>Fault</th>
                      <th>Correlation ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr
                        key={event.id}
                        className={`clickable ${event.delivery_success === false ? "delivery-row-failed" : ""}`}
                        onClick={() =>
                          navigate(`/simulations/${id}/events/${event.id}`)
                        }
                      >
                        <td>{formatTime(event.generated_at)}</td>
                        <td>
                          <HttpStatusCode code={event.response_status_code} />
                        </td>
                        <td>
                          {event.latency_ms != null
                            ? `${event.latency_ms} ms`
                            : "—"}
                        </td>
                        <td>{event.scenario_id}</td>
                        <td>{event.payload_source.replace(/_/g, " ")}</td>
                        <td>{event.fault_modified ? "modified" : "—"}</td>
                        <td
                          style={{
                            fontFamily: "var(--mono)",
                            fontSize: "0.75rem",
                          }}
                        >
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              void copyToClipboard(event.correlation_id);
                            }}
                          >
                            Copy
                          </button>{" "}
                          {event.correlation_id}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
