import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  deleteSimulation, importSimulation, listSimulations, sendSimulationEvent,
  startSimulation, stopSimulation,
} from "../api/simulations";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { StatusBadge } from "../components/StatusBadge";
import type { SimulationResponse } from "../types/api";
import { endpointLabel } from "../utils/endpoint";
import { formatApiError, formatDateTime, scenarioSummary } from "../utils/format";

function destinationLabel(sim: SimulationResponse): string {
  if (sim.simulation_mode === "pull_api") return "Mock API · Collector polls this simulator";
  if (sim.destination?.transport_id === "syslog") {
    return `Syslog ${sim.destination.protocol?.toUpperCase() ?? "UDP"} · ${sim.destination.host ?? "—"}:${sim.destination.port ?? 514}`;
  }
  return endpointLabel(sim.destination?.url);
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [simulations, setSimulations] = useState<SimulationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SimulationResponse | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setSimulations(await listSimulations());
      setError(null);
    } catch (err) { setError(formatApiError(err)); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const runAction = async (id: string, action: () => Promise<unknown>) => {
    setBusyId(id);
    setActionError(null);
    try { await action(); await load(); }
    catch (err) { setActionError(formatApiError(err)); }
    finally { setBusyId(null); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id);
    try {
      await deleteSimulation(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (err) { setActionError(formatApiError(err)); }
    finally { setBusyId(null); }
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setActionError(null);
    try {
      const document = JSON.parse(await file.text()) as Record<string, unknown>;
      const result = await importSimulation(document);
      await load();
      navigate(`/simulations/${result.simulation_id}`);
    } catch (err) { setActionError(formatApiError(err)); }
    finally { setImporting(false); }
  };

  const filtered = simulations.filter((sim) =>
    (status === "all" || sim.status === status) &&
    `${sim.name} ${sim.product_id} ${destinationLabel(sim)}`.toLowerCase().includes(query.trim().toLowerCase()),
  );

  if (loading) return <LoadingState label="Loading simulations…" />;

  return (
    <div>
      <div className="page-header">
        <div><p className="eyebrow">Workspace</p><h1>Simulations</h1>
          <p className="page-description">Configure integrations, send events, and see what happened.</p></div>
        <div className="page-actions">
          <input ref={importInputRef} type="file" accept="application/json,.json" hidden
            onChange={(event) => void handleImportFile(event)} />
          <button type="button" className="btn" disabled={importing}
            onClick={() => importInputRef.current?.click()}>{importing ? "Importing…" : "Import config"}</button>
          <Link to="/simulations/new" className="btn btn-primary"><Icon name="plus" />New simulation</Link>
        </div>
      </div>
      {error ? <ErrorAlert message={error} /> : null}
      {actionError ? <ErrorAlert message={actionError} /> : null}

      {simulations.length === 0 && !error ? (
        <section className="empty-state card" aria-labelledby="empty-heading">
          <span className="empty-mark"><Icon name="layers" /></span>
          <h2 id="empty-heading">Your first integration starts here</h2>
          <p>Create a simulation to send vendor events or let a collector poll a mock API.</p>
          <Link className="btn btn-primary" to="/simulations/new">Create a simulation<Icon name="arrow" /></Link>
          <div className="empty-alternatives"><Link to="/raw-logs">Generate a sample log</Link><span>or</span><Link to="/guides">Explore deployment guides</Link></div>
        </section>
      ) : (
        <>
          <div className="dashboard-toolbar">
            <div className="search-field"><Icon name="search" /><input type="search" aria-label="Search simulations"
              placeholder="Search by name, product, or destination…" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
            <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option><option value="running">Running</option>
              <option value="stopped">Stopped</option><option value="completed">Completed</option><option value="error">Error</option>
            </select>
            <button className="btn" type="button" onClick={() => void load()} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh"}</button>
          </div>
          <p className="result-count" role="status">{filtered.length} of {simulations.length} simulations{simulations.some((sim) => sim.status === "running") ? ` · ${simulations.filter((sim) => sim.status === "running").length} running` : ""}</p>
          {filtered.length === 0 ? (
            <div className="card empty-state"><h2>{error ? "Unable to load simulations" : "No matching simulations"}</h2>
              <p>{error ? "Use Refresh to try again." : "Try a different name, product, destination, or status."}</p>
              {!error && <button type="button" className="btn" onClick={() => { setQuery(""); setStatus("all"); }}>Clear filters</button>}
            </div>
          ) : (
            <ul className="simulation-list" aria-label="Simulations">
              {filtered.map((sim) => {
                const manual = sim.simulation_mode !== "pull_api" && sim.schedule?.type === "manual";
                const running = sim.status === "running";
                const action = running ? "Stop" : manual ? "Send" : "Start";
                const blocked = !running && sim.missing_secrets.length > 0;
                return (
                  <li key={sim.id} className="simulation-item">
                    <div className="simulation-identity"><span className="product-mark"><Icon name={sim.simulation_mode === "pull_api" ? "code" : "layers"} /></span>
                      <div><Link className="simulation-name" to={`/simulations/${sim.id}`}>{sim.name}</Link>
                        <div className="simulation-meta"><span>{sim.product_id}</span><span>{sim.simulation_mode === "pull_api" ? "Pull API" : manual ? "Manual send" : "Scheduled push"}</span></div>
                        <p className="simulation-destination">{destinationLabel(sim)}</p>
                        <span className="sr-only">{scenarioSummary(sim.scenario_ids)}</span>
                      </div>
                    </div>
                    <div className="simulation-state"><StatusBadge status={sim.status} />
                      {blocked && <span className="field-error" id={`blocked-${sim.id}`}>Add missing credentials in Edit before sending.</span>}
                    </div>
                    <div className="simulation-delivery"><span><strong>{sim.runtime_stats.events_successful.toLocaleString()}</strong> accepted <span className={sim.runtime_stats.events_failed ? "failed-count" : ""}>· {sim.runtime_stats.events_failed.toLocaleString()} failed</span></span>
                      <small>Last delivery: {formatDateTime(sim.runtime_stats.last_delivery_at)}</small>
                    </div>
                    <div className="simulation-actions">
                      <button type="button" className={`btn ${running ? "" : "btn-primary"}`} disabled={busyId !== null || blocked}
                        aria-describedby={blocked ? `blocked-${sim.id}` : undefined}
                        onClick={() => void runAction(sim.id, () => running ? stopSimulation(sim.id) : manual ? sendSimulationEvent(sim.id) : startSimulation(sim.id))}>
                        {busyId === sim.id ? "Working…" : action}
                      </button>
                      <details className="action-menu" onKeyDown={(event) => {
                        if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); }
                      }}>
                        <summary aria-label={`More actions for ${sim.name}`}>More<span aria-hidden="true">⌄</span></summary>
                        <div className="action-menu-panel">
                          <Link to={`/simulations/${sim.id}`}>Open details</Link>
                          {running ? <span className="menu-hint">Stop to edit or delete</span> : <Link to={`/simulations/${sim.id}/edit`}>Edit</Link>}
                          {!manual && sim.simulation_mode !== "pull_api" && <button type="button" disabled={busyId !== null || sim.missing_secrets.length > 0}
                            onClick={() => void runAction(sim.id, () => sendSimulationEvent(sim.id))}>Send one event</button>}
                          <button type="button" className="menu-danger" disabled={busyId !== null || running}
                            onClick={(event) => { const menu = event.currentTarget.closest("details"); menu?.removeAttribute("open"); menu?.querySelector("summary")?.focus(); setDeleteTarget(sim); }}>Delete</button>
                        </div>
                      </details>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="dashboard-note">Delivery acceptance does not confirm downstream ingestion or vendor parser compatibility.</p>
        </>
      )}
      {deleteTarget && <ConfirmDialog title="Delete simulation?" message={`Permanently delete "${deleteTarget.name}" and all event history?`}
        onConfirm={() => void handleDelete()} onCancel={() => setDeleteTarget(null)} loading={busyId === deleteTarget.id} />}
    </div>
  );
}
