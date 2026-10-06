import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAnyInboundRequest, getInboundRequest } from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode } from "../components/StatusBadge";
import { JsonViewer } from "../components/JsonViewer";
import type { InboundRequestDetail } from "../types/api";
import { formatApiError, formatDateTime } from "../utils/format";

export function InboundRequestDetailPage() {
  const { id, requestId } = useParams<{ id: string; requestId: string }>();
  const [request, setRequest] = useState<InboundRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!requestId) return;
    const loader = id ? getInboundRequest(id, requestId) : getAnyInboundRequest(requestId);
    void loader
      .then(setRequest)
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, [id, requestId]);

  if (loading) return <LoadingState label="Loading inbound request…" />;
  if (error && !request) return <ErrorAlert message={error} />;
  if (!request) return <ErrorAlert message="Inbound request not found" />;

  let responseJson: unknown = request.response_body;
  try {
    if (request.response_body) {
      responseJson = JSON.parse(request.response_body);
    }
  } catch {
    responseJson = request.response_body;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Inbound Request</h1>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {formatDateTime(request.received_at)} ·{" "}
            <HttpStatusCode code={request.response_status_code} /> · {request.latency_ms} ms
          </p>
        </div>
        <Link to={id ? `/simulations/${id}` : "/inbound-requests"} className="btn">
          {id ? "Back to simulation" : "Back to all requests"}
        </Link>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <dl className="detail-grid">
          <dt>Method</dt>
          <dd>{request.request_method}</dd>
          <dt>Path</dt>
          <dd style={{ fontFamily: "var(--mono)", fontSize: "0.8125rem" }}>{request.request_path}</dd>
          <dt>Route</dt>
          <dd>{request.route_id}</dd>
          <dt>Auth</dt>
          <dd>
            {request.auth_method_id} ({request.auth_result})
          </dd>
          <dt>Items returned</dt>
          <dd>{request.items_returned}</dd>
          {request.token_metadata ? (
            <>
              <dt>Token metadata</dt>
              <dd>
                <JsonViewer data={request.token_metadata} />
              </dd>
            </>
          ) : null}
          {request.error_message ? (
            <>
              <dt>Error</dt>
              <dd>{request.error_message}</dd>
            </>
          ) : null}
        </dl>
      </div>

      <div className="grid-2" style={{ gap: "1rem" }}>
        <div className="card">
          <h2 style={{ fontSize: "1rem" }}>Query parameters</h2>
          <JsonViewer data={request.request_query_params} />
        </div>
        <div className="card">
          <h2 style={{ fontSize: "1rem" }}>Request headers (redacted)</h2>
          <JsonViewer data={request.request_headers_redacted} />
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ fontSize: "1rem" }}>Response body</h2>
        <JsonViewer data={responseJson} />
      </div>
    </div>
  );
}
