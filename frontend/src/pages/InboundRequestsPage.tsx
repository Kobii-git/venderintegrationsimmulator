import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { listAllInboundRequests } from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode } from "../components/StatusBadge";
import type { InboundRequestSummary } from "../types/api";
import { formatApiError, formatTime } from "../utils/format";

export function InboundRequestsPage() {
  const loadVersion = useRef(0);
  const [requests, setRequests] = useState<InboundRequestSummary[]>([]);
  const [simulationId, setSimulationId] = useState("");
  const [requestKind, setRequestKind] = useState("");
  const [responseStatus, setResponseStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    try {
      const result = await listAllInboundRequests({
          simulation_id: simulationId || undefined,
          request_kind: requestKind || undefined,
          response_status: responseStatus ? Number(responseStatus) : undefined,
        });
      if (version !== loadVersion.current) return;
      setRequests(result); setError(null);
    } catch (loadError) {
      if (version === loadVersion.current) setError(formatApiError(loadError));
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [requestKind, responseStatus, simulationId]);

  useEffect(() => {
    void load();
    return () => { loadVersion.current += 1; };
  }, [load]);

  if (loading) return <LoadingState label="Loading inbound requests…" />;

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Request monitoring</p><h1>Inbound Requests</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            Global pull API, authentication, fault, and unmatched request audit.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void load()}>Refresh requests</button>
      </div>
      {error ? <ErrorAlert message={error} /> : null}
      <div className="card">
        <div className="grid-2" style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <label htmlFor="global-simulation-filter">Simulation ID</label>
            <input
              id="global-simulation-filter"
              placeholder="All, including unmatched"
              value={simulationId}
              onChange={(event) => setSimulationId(event.target.value)}
            />
          </div>
          <div className="form-row">
            <label htmlFor="global-kind-filter">Kind</label>
            <select
              id="global-kind-filter"
              value={requestKind}
              onChange={(event) => setRequestKind(event.target.value)}
            >
              <option value="">All</option>
              <option value="api">API</option>
              <option value="token">OAuth token</option>
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="global-status-filter">Response status</label>
            <input
              id="global-status-filter"
              type="number"
              min={100}
              max={599}
              value={responseStatus}
              onChange={(event) => setResponseStatus(event.target.value)}
            />
          </div>
        </div>
        <div className="monitor-history-toolbar"><span className="form-hint">{requests.length} recent matching requests. Select a time to inspect authentication and response details.</span>
          <button type="button" className="btn btn-sm" onClick={() => { setSimulationId(""); setRequestKind(""); setResponseStatus(""); }}>Clear filters</button></div>
        {requests.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Simulation</th>
                  <th>Product / route</th>
                  <th>Status</th>
                  <th>Auth</th>
                  <th>Items</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((request) => (
                  <tr key={request.id}>
                    <td><Link to={`/inbound-requests/${request.id}`}>{formatTime(request.received_at)}</Link></td>
                    <td>{request.simulation_id ?? <strong>Unmatched</strong>}</td>
                    <td>{request.product_id} / {request.route_id}</td>
                    <td><HttpStatusCode code={request.response_status_code} /></td>
                    <td>{request.auth_method_id} ({request.auth_result})</td>
                    <td>{request.items_returned}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)" }}>No requests match these filters.</p>
        )}
      </div>
    </div>
  );
}
