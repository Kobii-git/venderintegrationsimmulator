import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { getAnyInboundRequest, getInboundRequest } from "../api/simulations";
import { BodyEvidence } from "../components/BodyEvidence";
import { ConsoleTabs } from "../components/ConsoleTabs";
import { ErrorAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode } from "../components/StatusBadge";
import { JsonViewer } from "../components/JsonViewer";
import type { InboundRequestDetail } from "../types/api";
import { formatApiError, formatDateTime } from "../utils/format";

export function InboundRequestDetailPage() {
  const { id, requestId } = useParams<{ id: string; requestId: string }>();
  const [params] = useSearchParams();
  const [request, setRequest] = useState<InboundRequestDetail | null>(null);
  const [view, setView] = useState("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const back = id ? `/simulations/${id}?view=activity` : `/inbound-requests${params.size ? `?${params.toString()}` : ""}`;
  useEffect(() => {
    if (!requestId) return;
    let active = true;
    setRequest(null); setError(null); setLoading(true); setView("summary");
    void (id ? getInboundRequest(id, requestId) : getAnyInboundRequest(requestId))
      .then((value) => { if (active) setRequest(value); })
      .catch((err) => { if (active) setError(formatApiError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, requestId, retry]);
  if (loading) return <LoadingState label="Loading inbound request…" />;
  if (!request) return <div><ErrorAlert message={error ?? "Inbound request not found"} /><div className="page-actions"><Link className="btn" to={back}>Back to request history</Link><button className="btn" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></div></div>;
  const failed = request.response_status_code >= 400;
  return <div>
    <div className="page-header"><div><p className="eyebrow">Request inspection</p><h1>Inbound Request</h1><p className="page-description">{formatDateTime(request.received_at)} · {request.request_kind === "token" ? "OAuth token request" : "API request"}</p></div>
      <Link to={back} className="btn">{id ? "Back to simulation" : "Back to all requests"}</Link></div>
    <div className={`delivery-outcome ${failed ? "is-failed" : "is-success"}`} role={failed ? "alert" : "status"}>
      <h2>{failed ? "Request failed" : request.response_status_code < 300 ? "Request accepted" : "Request recorded"} <HttpStatusCode code={request.response_status_code} /></h2>
      <p>{request.error_message ?? (request.auth_result === "unmatched" ? "No simulation matched this call. Check the endpoint and simulation ID." : failed ? "Inspect authentication, query parameters and the recorded response below." : "The mock API recorded this response. Items returned does not confirm downstream ingestion.")}</p>
    </div>
    <div className="metric-grid"><div className="metric"><span>Authentication</span><strong className="metric-text">{request.auth_result === "success" ? request.auth_method_id === "none" ? "Not required" : "Passed" : request.auth_result === "failed" ? "Rejected" : request.auth_result}</strong></div><div className="metric"><span>Latency</span><strong>{request.latency_ms}<small> ms</small></strong></div><div className="metric"><span>Items returned</span><strong>{request.items_returned}</strong></div><div className="metric"><span>Request method</span><strong className="metric-text">{request.request_method}</strong></div></div>
    <ConsoleTabs id="inbound" label="Request evidence" value={view} onChange={setView} tabs={[{ id: "summary", label: "Summary" }, { id: "request", label: "Request" }, { id: "response", label: "Response" }]} />
    <div key={request.id}>
    <section role="tabpanel" id="inbound-panel-summary" aria-labelledby="inbound-tab-summary" hidden={view !== "summary"}><div className="card"><h2>Request summary</h2><dl className="detail-grid">
      <dt>Path</dt><dd className="mono-field">{request.request_path}</dd><dt>Product / route</dt><dd>{request.product_id} / {request.route_id}</dd>
      <dt>Simulation</dt><dd>{request.simulation_id ? <Link to={`/simulations/${request.simulation_id}?view=activity`}>{request.simulation_id}</Link> : "Unmatched — no simulation was selected"}</dd>
      <dt>Authentication method</dt><dd>{request.auth_method_id}</dd><dt>Authentication result</dt><dd>{request.auth_result}</dd><dt>Request ID</dt><dd className="mono-field">{request.id}</dd>
    </dl></div>{request.token_metadata && <div className="card"><h2>Token metadata</h2><JsonViewer data={request.token_metadata} label="Recorded token metadata" /></div>}</section>
    <section role="tabpanel" id="inbound-panel-request" aria-labelledby="inbound-tab-request" hidden={view !== "request"}><div className="evidence-grid"><div className="card"><h2>Query parameters</h2><JsonViewer data={request.request_query_params} label="Recorded query parameters" /></div><div className="card"><h2>Request headers (redacted)</h2><JsonViewer data={request.request_headers_redacted} label="Recorded request headers" /></div></div><div className="card"><h2>Request body</h2><BodyEvidence body={request.request_body} label="Recorded request body" /></div></section>
    <section role="tabpanel" id="inbound-panel-response" aria-labelledby="inbound-tab-response" hidden={view !== "response"}><div className="card"><h2>Response headers</h2><JsonViewer data={request.response_headers} label="Recorded response headers" /></div><div className="card"><h2>Response body</h2><BodyEvidence body={request.response_body} label="Recorded response body" /></div></section>
    </div>
  </div>;
}
