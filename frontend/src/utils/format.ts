import { ApiError } from "../api/client";

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details && "errors" in error.details) {
      return `${error.message} (${JSON.stringify(error.details.errors)})`;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}

function apiDate(iso: string): Date | null {
  // SQLite serializes UTC database timestamps without an offset; runtime timestamps include one.
  const utc = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(iso) ? `${iso}Z` : iso;
  const date = new Date(utc);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return apiDate(iso)?.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }) ?? "—";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return apiDate(iso)?.toLocaleString() ?? "—";
}

export function scenarioSummary(ids: string[]): string {
  if (ids.length === 0) return "—";
  if (ids.length === 1) return ids[0];
  return `${ids.length} scenarios (${ids.slice(0, 2).join(", ")}${ids.length > 2 ? "…" : ""})`;
}

export async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}
