import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listAllInboundRequests, listSimulations } from "../api/simulations";
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { HttpStatusCode } from "../components/StatusBadge";
import type { InboundRequestSummary, SimulationResponse } from "../types/api";
import { formatApiError, formatDateTime, formatTime } from "../utils/format";

export function InboundRequestsPage() {
  const [params, setParams] = useSearchParams();
  const simulationId = params.get("simulation") ?? "";
  const requestKind = params.get("kind") ?? "";
  const responseStatus = params.get("status") ?? "";
  const query = params.get("q") ?? "";
  const [draftSimulation, setDraftSimulation] = useState(simulationId);
  const [draftKind, setDraftKind] = useState(requestKind);
  const [draftStatus, setDraftStatus] = useState(responseStatus);
  const loadVersion = useRef(0);
  const [requests, setRequests] = useState<InboundRequestSummary[]>([]);
  const [simulations, setSimulations] = useState<SimulationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const validStatus = !responseStatus || (/^\d{3}$/.test(responseStatus) && Number(responseStatus) >= 100 && Number(responseStatus) <= 599);

  useEffect(() => { setDraftSimulation(simulationId); setDraftKind(requestKind); setDraftStatus(responseStatus); }, [simulationId, requestKind, responseStatus]);
  useEffect(() => {
    let active = true;
    // Names enrich the audit. History remains available if a simulation was deleted or this lookup fails.
    void listSimulations().then((value) => { if (active) setSimulations(value); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    if (!validStatus) { setLoading(false); setError("Response status must be a whole HTTP code from 100 to 599. Correct it and apply filters."); return; }
    setRefreshing(true);
    try {
      const result = await listAllInboundRequests({ limit: 100, simulation_id: simulationId || undefined, request_kind: requestKind || undefined, response_status: responseStatus ? Number(responseStatus) : undefined });
      if (version !== loadVersion.current) return;
      setRequests(result); setError(null); setLastUpdated(new Date().toISOString());
    } catch (err) { if (version === loadVersion.current) setError(formatApiError(err)); }
    finally { if (version === loadVersion.current) { setLoading(false); setRefreshing(false); } }
  }, [simulationId, requestKind, responseStatus, validStatus]);
  useEffect(() => { setRequests([]); setLoading(true); void load(); return () => { loadVersion.current += 1; }; }, [load]);
  const clear = () => { setDraftSimulation(""); setDraftKind(""); setDraftStatus(""); setParams({}); };
  const names = new Map(simulations.map((simulation) => [simulation.id, simulation.name]));
  const options = new Map(names);
  requests.forEach((request) => { if (request.simulation_id && !options.has(request.simulation_id)) options.set(request.simulation_id, `Saved ID · ${request.simulation_id}`); });
  if (simulationId && !options.has(simulationId)) options.set(simulationId, `Saved ID · ${simulationId}`);
  const visible = requests.filter((request) => `${names.get(request.simulation_id ?? "") ?? ""} ${request.simulation_id ?? "unmatched"} ${request.product_id} ${request.route_id} ${request.request_method} ${request.request_path} ${request.auth_result} ${request.error_message ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filtersActive = !!(simulationId || requestKind || responseStatus || query);
  const suffix = params.size ? `?${params.toString()}` : "";

  return <div>
    <div className="page-header"><div><p className="eyebrow">Request monitoring</p><h1>Inbound Requests</h1><p className="page-description">Trace collector polling, authentication and unmatched calls across your workspace.</p></div>
      <div className="page-actions"><Link className="btn" to="/">Open simulations</Link><button type="button" className="btn" disabled={refreshing || !validStatus} onClick={() => void load()}>{refreshing ? "Refreshing…" : "Refresh requests"}</button></div></div>
    <div className="tool-notice"><Icon name="activity" /><span>History updates on refresh. Open a request to inspect its authentication and response evidence.</span></div>
    <form className="card request-filters" aria-label="Request filters" onSubmit={(event) => {
      event.preventDefault(); const next = new URLSearchParams(params);
      for (const [key, value] of [["simulation", draftSimulation], ["kind", draftKind], ["status", draftStatus]]) { if (value) next.set(key, value); else next.delete(key); }
      if (next.toString() === params.toString()) void load(); else setParams(next);
    }}>
      <div className="request-filter-grid"><div className="form-row"><label htmlFor="global-simulation-filter">Simulation</label><select id="global-simulation-filter" value={draftSimulation} onChange={(event) => setDraftSimulation(event.target.value)}><option value="">All, including unmatched</option>{[...options].sort((a,b) => a[1].localeCompare(b[1])).map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></div>
      <div className="form-row"><label htmlFor="global-kind-filter">Kind</label><select id="global-kind-filter" value={draftKind} onChange={(event) => setDraftKind(event.target.value)}><option value="">All requests</option><option value="api">API</option><option value="token">OAuth token</option></select></div>
      <div className="form-row"><label htmlFor="global-status-filter">Response status</label><input id="global-status-filter" type="number" min={100} max={599} step={1} placeholder="Any, e.g. 401" value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)} /></div></div>
      <div className="request-filter-actions"><span className="form-hint">Filters fetch the latest 100 matching requests. Search below narrows that loaded set.</span><div className="page-actions"><button type="button" className="btn" onClick={clear}>Clear filters</button><button type="submit" className="btn btn-primary">Apply filters</button></div></div>
    </form>
    {error && <ErrorAlert message={error} />}
    <div className="metric-grid request-metrics" aria-label="Loaded request summary"><div className="metric"><span>Loaded requests</span><strong>{requests.length}</strong></div><div className="metric"><span>HTTP errors</span><strong>{requests.filter((request) => request.response_status_code >= 400).length}</strong></div><div className="metric"><span>Authentication failures</span><strong>{requests.filter((request) => request.auth_result === "failed").length}</strong></div><div className="metric"><span>Unmatched calls</span><strong>{requests.filter((request) => !request.simulation_id).length}</strong></div></div>
    <section className="card request-history" aria-label="Request history" aria-busy={refreshing}>
      <div className="request-history-heading"><div><h2>Recent requests</h2><p className="form-hint">{lastUpdated ? `Last refreshed ${formatTime(lastUpdated)}` : "Waiting for request history"}</p></div><div className="form-row"><label htmlFor="request-search">Search recent requests</label><input id="request-search" type="search" placeholder="Path, product, simulation or error" value={query} onChange={(event) => { const next = new URLSearchParams(params); if (event.target.value) next.set("q", event.target.value); else next.delete("q"); setParams(next, { replace: true }); }} /></div></div>
      {loading ? <LoadingState label="Loading inbound requests…" /> : <>
      <p className="form-hint" role="status">{visible.length} of {requests.length} loaded requests shown{requests.length === 100 ? " · Limit reached; narrow the filters for older requests." : "."}</p>
      {visible.length ? <div className="table-wrap" role="region" aria-label="Scrollable request history" tabIndex={0}><table className="data-table request-table"><thead><tr><th>Time / request</th><th>Simulation</th><th>Product / route</th><th>Response</th><th>Authentication</th><th>Items</th></tr></thead><tbody>
        {visible.map((request) => <tr key={request.id} className={request.response_status_code >= 400 ? "delivery-row-failed" : undefined}>
          <td><Link to={`/inbound-requests/${request.id}${suffix}`}>{formatDateTime(request.received_at)}</Link><span className="table-secondary mono-field">{request.request_method} {request.request_path}</span></td>
          <td>{request.simulation_id ? <><span>{names.get(request.simulation_id) ?? "Saved simulation"}</span><span className="table-secondary mono-field">{request.simulation_id}</span></> : <span className="badge badge-stopped">Unmatched</span>}</td>
          <td>{request.product_id}<span className="table-secondary">{request.route_id} · {request.request_kind === "token" ? "OAuth token" : "API"}</span></td>
          <td><HttpStatusCode code={request.response_status_code} /><span className="table-secondary">{request.latency_ms} ms</span></td>
          <td><span className={`badge ${request.auth_result === "failed" ? "badge-failed" : request.auth_result === "success" ? "badge-success" : "badge-stopped"}`}>{request.auth_result === "success" ? request.auth_method_id === "none" ? "Not required" : "Authenticated" : request.auth_result === "failed" ? "Rejected" : request.auth_result}</span><span className="table-secondary">{request.auth_method_id}</span></td><td>{request.items_returned}</td>
        </tr>)}
      </tbody></table></div> : <div className="empty-state"><span className="empty-mark"><Icon name="activity" /></span><h3>{error ? "Request history unavailable" : filtersActive ? "No matching requests" : "No inbound requests yet"}</h3><p>{error ? "Refresh to try again. Existing audit data is retained on the server." : filtersActive ? "Clear or adjust your filters, or refresh after your collector makes another call." : "Start a pull API simulation and poll its mock endpoint from your collector. Authentication and unmatched calls will appear here too."}</p>{filtersActive ? <button type="button" className="btn" onClick={clear}>Reset request filters</button> : <Link className="btn" to="/">Choose a simulation<Icon name="arrow" /></Link>}</div>}
      </>}
    </section>
  </div>;
}
