import type { SimulationStatus } from "../types/api";

const CLASS_MAP: Record<SimulationStatus, string> = {
  stopped: "badge-stopped",
  running: "badge-running",
  completed: "badge-completed",
  error: "badge-error",
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const cls = CLASS_MAP[status as SimulationStatus] ?? "badge-stopped";
  return <span className={`badge ${cls}`}>{status}</span>;
}

interface DeliveryBadgeProps {
  success: boolean | null;
}

export function DeliveryBadge({ success }: DeliveryBadgeProps) {
  if (success === null) return <span className="badge badge-stopped">pending</span>;
  return (
    <span className={`badge ${success ? "badge-success" : "badge-failed"}`}>
      {success ? "success" : "failed"}
    </span>
  );
}

interface HttpStatusCodeProps {
  code: number | null | undefined;
}

export function HttpStatusCode({ code }: HttpStatusCodeProps) {
  if (code == null) return <span className="status-code">—</span>;
  const ok = code >= 200 && code < 300;
  return <span className={`status-code ${ok ? "ok" : "fail"}`}>{code}</span>;
}
