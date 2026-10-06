import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  deleteSimulation,
  importSimulation,
  listSimulations,
  sendSimulationEvent,
  startSimulation,
  stopSimulation,
} from "../api/simulations";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { StatusBadge } from "../components/StatusBadge";
import type { SimulationResponse } from "../types/api";
import { formatApiError, formatDateTime, scenarioSummary } from "../utils/format";

export function DashboardPage() {
  const navigate = useNavigate();
  const [simulations, setSimulations] = useState<SimulationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SimulationResponse | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    try {
      setSimulations(await listSimulations());
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = async (id: string, action: () => Promise<unknown>) => {
    setBusyId(id);
    setActionError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setActionError(formatApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id);
    try {
      await deleteSimulation(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setActionError(formatApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setImporting(true);
    setActionError(null);
    try {
      const text = await file.text();
      const document = JSON.parse(text) as Record<string, unknown>;
      const result = await importSimulation(document);
      await load();
      navigate(`/simulations/${result.simulation_id}`);
    } catch (err) {
      setActionError(formatApiError(err));
    } finally {
      setImporting(false);
    }
  };

  if (loading) return <LoadingState label="Loading simulations…" />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Simulations</h1>
          <p style={{ color: "var(--text-muted)", margin: 0 }}>
            Manage webhook simulations and monitor delivery activity.
          </p>
        </div>
        <div className="page-actions">
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(event) => void handleImportFile(event)}
          />
          <button
            type="button"
            className="btn"
            disabled={importing}
            onClick={() => importInputRef.current?.click()}
          >
            {importing ? "Importing…" : "Import config"}
          </button>
          <Link to="/simulations/new" className="btn btn-primary">
            New Simulation
          </Link>
        </div>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {actionError ? <ErrorAlert message={actionError} /> : null}

      <div className="card">
        {simulations.length === 0 ? (
          <p style={{ color: "var(--text-muted)" }}>
            No simulations yet.{" "}
            <Link to="/simulations/new">Create one</Link> to start sending events.
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Product</th>
                  <th>Status</th>
                  <th>Destination</th>
                  <th>Scenarios</th>
                  <th>OK</th>
                  <th>Failed</th>
                  <th>Last Activity</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {simulations.map((sim) => (
                  <tr key={sim.id}>
                    <td>
                      <Link to={`/simulations/${sim.id}`}>
                        <strong>{sim.name}</strong>
                      </Link>
                    </td>
                    <td>
                      {sim.product_id}
                      <span style={{ color: "var(--text-muted)", marginLeft: "0.5rem" }}>
                        ({sim.simulation_mode === "pull_api" ? "pull" : "push"})
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={sim.status} />
                    </td>
                    <td style={{ fontFamily: "var(--mono)", fontSize: "0.8125rem" }}>
                      {sim.destination?.transport_id === "syslog"
                        ? `${sim.destination.host ?? "—"}:${sim.destination.port ?? 514}`
                        : sim.simulation_mode === "pull_api"
                          ? `/api/v1/mock/${sim.product_id}/…`
                          : (sim.destination?.url ?? "—")}
                    </td>
                    <td>{scenarioSummary(sim.scenario_ids)}</td>
                    <td className="stat-value success" style={{ fontSize: "0.875rem" }}>
                      {sim.runtime_stats.events_successful}
                    </td>
                    <td className="stat-value failed" style={{ fontSize: "0.875rem" }}>
                      {sim.runtime_stats.events_failed}
                    </td>
                    <td>{formatDateTime(sim.runtime_stats.last_delivery_at)}</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => navigate(`/simulations/${sim.id}`)}
                        >
                          Open
                        </button>
                        {sim.status !== "running" ? (
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={
                              busyId === sim.id ||
                              (sim.simulation_mode !== "pull_api" &&
                                sim.schedule?.type === "manual") ||
                              sim.missing_secrets.length > 0
                            }
                            title={
                              sim.missing_secrets.length
                                ? `Missing: ${sim.missing_secrets.join(", ")}`
                                : sim.simulation_mode !== "pull_api" &&
                                    sim.schedule?.type === "manual"
                                  ? "Manual push simulations use Send"
                                  : undefined
                            }
                            onClick={() => void runAction(sim.id, () => startSimulation(sim.id))}
                          >
                            Start
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={busyId === sim.id}
                            onClick={() => void runAction(sim.id, () => stopSimulation(sim.id))}
                          >
                            Stop
                          </button>
                        )}
                        {sim.simulation_mode !== "pull_api" ? (
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={busyId === sim.id || sim.missing_secrets.length > 0}
                            onClick={() =>
                              void runAction(sim.id, () => sendSimulationEvent(sim.id))
                            }
                          >
                            Send
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={sim.status === "running"}
                          onClick={() => navigate(`/simulations/${sim.id}/edit`)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          disabled={busyId === sim.id || sim.status === "running"}
                          onClick={() => setDeleteTarget(sim)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {deleteTarget ? (
        <ConfirmDialog
          title="Delete simulation?"
          message={`Permanently delete "${deleteTarget.name}" and all event history?`}
          onConfirm={() => void handleDelete()}
          onCancel={() => setDeleteTarget(null)}
          loading={busyId === deleteTarget.id}
        />
      ) : null}
    </div>
  );
}
