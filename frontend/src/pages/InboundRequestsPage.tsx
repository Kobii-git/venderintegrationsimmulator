import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listAllInboundRequests } from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode } from "../components/StatusBadge";
import type { InboundRequestSummary } from "../types/api";
import { formatApiError, formatTime } from "../utils/format";

export function InboundRequestsPage() {
  const navigate = useNavigate();
  const [requests, setRequests] = useState<InboundRequestSummary[]>([]);
  const [simulationId, setSimulationId] = useState("");
  const [requestKind, setRequestKind] = useState("");
  const [responseStatus, setResponseStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRequests(
        await listAllInboundRequests({
          simulation_id: simulationId || undefined,
          request_kind: requestKind || undefined,
          response_status: responseStatus ? Number(responseStatus) : undefined,
        }),
      );
      setError(null);
    } catch (loadError) {
      setError(formatApiError(loadError));
    } finally {
      setLoading(false);
    }
  }, [requestKind, responseStatus, simulationId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading inbound requests…" />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Inbound Requests</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            Global pull API, authentication, fault, and unmatched request audit.
          </p>
        </div>
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
                  <tr
                    key={request.id}
                    className="clickable"
                    onClick={() => navigate(`/inbound-requests/${request.id}`)}
                  >
                    <td>{formatTime(request.received_at)}</td>
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
