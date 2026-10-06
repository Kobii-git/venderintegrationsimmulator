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

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function scenarioSummary(ids: string[]): string {
  if (ids.length === 0) return "—";
  if (ids.length === 1) return ids[0];
  return `${ids.length} scenarios (${ids.slice(0, 2).join(", ")}${ids.length > 2 ? "…" : ""})`;
}

export async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}
