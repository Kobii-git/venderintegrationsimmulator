import { del, get, patch, post } from "./client";
import type {
  CurlResponse,
  EventInstanceDetail,
  EventInstanceSummary,
  EventListFilters,
  InboundEndpointInfo,
  InboundRequestDetail,
  InboundRequestSummary,
  IssuedOAuthToken,
  ReplayEventRequest,
  ReplayEventResponse,
  SimulationBurstRequest,
  SimulationBurstResponse,
  SimulationCreate,
  SimulationResponse,
  SimulationSendRequestBody,
  SimulationSendResponse,
  SimulationUpdate,
  WorkflowActionResponse,
} from "../types/api";

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listSimulations(): Promise<SimulationResponse[]> {
  return get<SimulationResponse[]>("/simulations");
}

export function getSimulation(id: string): Promise<SimulationResponse> {
  return get<SimulationResponse>(`/simulations/${id}`);
}

export function createSimulation(data: SimulationCreate): Promise<SimulationResponse> {
  return post<SimulationResponse>("/simulations", data);
}

export function updateSimulation(id: string, data: SimulationUpdate): Promise<SimulationResponse> {
  return patch<SimulationResponse>(`/simulations/${id}`, data);
}

export function deleteSimulation(id: string): Promise<void> {
  return del(`/simulations/${id}`);
}

export function startSimulation(id: string): Promise<SimulationResponse> {
  return post<SimulationResponse>(`/simulations/${id}/start`);
}

export function stopSimulation(id: string): Promise<SimulationResponse> {
  return post<SimulationResponse>(`/simulations/${id}/stop`);
}

export function sendSimulationEvent(
  id: string,
  body?: SimulationSendRequestBody,
): Promise<SimulationSendResponse> {
  return post<SimulationSendResponse>(`/simulations/${id}/send`, body ?? {});
}

export function executeSimulationAction(
  id: string,
  actionId: string,
): Promise<WorkflowActionResponse> {
  return post<WorkflowActionResponse>(
    `/simulations/${id}/actions/${encodeURIComponent(actionId)}`,
  );
}

export function listSimulationEvents(
  id: string,
  filters: EventListFilters = {},
): Promise<EventInstanceSummary[]> {
  const query = buildQuery({
    limit: filters.limit ?? 100,
    scenario_id: filters.scenario_id,
    success: filters.success,
    http_status: filters.http_status,
    correlation_id: filters.correlation_id,
  });
  return get<EventInstanceSummary[]>(`/simulations/${id}/events${query}`);
}

export function getSimulationEvent(
  simulationId: string,
  eventId: string,
): Promise<EventInstanceDetail> {
  return get<EventInstanceDetail>(`/simulations/${simulationId}/events/${eventId}`);
}

export function getSimulationEventCurl(
  simulationId: string,
  eventId: string,
  attemptId?: string,
): Promise<CurlResponse> {
  const query = attemptId ? `?attempt_id=${encodeURIComponent(attemptId)}` : "";
  return get<CurlResponse>(`/simulations/${simulationId}/events/${eventId}/curl${query}`);
}

export function replaySimulationEvent(
  simulationId: string,
  eventId: string,
  body: ReplayEventRequest,
): Promise<ReplayEventResponse> {
  return post<ReplayEventResponse>(
    `/simulations/${simulationId}/events/${eventId}/replay`,
    body,
  );
}

export function findEventsByCorrelationId(
  correlationId: string,
  limit = 20,
): Promise<EventInstanceSummary[]> {
  return get<EventInstanceSummary[]>(
    `/events${buildQuery({ correlation_id: correlationId, limit })}`,
  );
}

export function burstSimulationEvents(
  id: string,
  body: SimulationBurstRequest,
): Promise<SimulationBurstResponse> {
  return post<SimulationBurstResponse>(`/simulations/${id}/burst`, body);
}

export function exportSimulation(
  id: string,
  includeSecrets = false,
  confirmSecretExport = false,
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams();
  if (includeSecrets) params.set("include_secrets", "true");
  if (confirmSecretExport) params.set("confirm_secret_export", "true");
  const query = params.toString();
  return get<Record<string, unknown>>(
    `/simulations/${id}/export${query ? `?${query}` : ""}`,
  );
}

export function importSimulation(
  document: Record<string, unknown>,
): Promise<{
  simulation_id: string;
  name: string;
  secrets_imported: boolean;
  missing_secrets: string[];
}> {
  return post("/simulations/import", { document });
}

export function getInboundEndpointInfo(id: string): Promise<InboundEndpointInfo> {
  return get<InboundEndpointInfo>(`/simulations/${id}/inbound-endpoint`);
}

export function listInboundRequests(
  id: string,
  limit = 50,
  requestKind?: string,
): Promise<InboundRequestSummary[]> {
  const kind = requestKind ? `&request_kind=${encodeURIComponent(requestKind)}` : "";
  return get<InboundRequestSummary[]>(
    `/simulations/${id}/inbound-requests?limit=${limit}${kind}`,
  );
}

export function listOAuthTokens(id: string, limit = 50): Promise<IssuedOAuthToken[]> {
  return get<IssuedOAuthToken[]>(`/simulations/${id}/oauth-tokens?limit=${limit}`);
}

export function getInboundRequest(
  simulationId: string,
  requestId: string,
): Promise<InboundRequestDetail> {
  return get<InboundRequestDetail>(
    `/simulations/${simulationId}/inbound-requests/${requestId}`,
  );
}

export function listAllInboundRequests(filters: {
  limit?: number;
  simulation_id?: string;
  request_kind?: string;
  response_status?: number;
} = {}): Promise<InboundRequestSummary[]> {
  return get<InboundRequestSummary[]>(
    `/inbound-requests${buildQuery({
      limit: filters.limit ?? 100,
      simulation_id: filters.simulation_id,
      request_kind: filters.request_kind,
      response_status: filters.response_status,
    })}`,
  );
}

export function getAnyInboundRequest(requestId: string): Promise<InboundRequestDetail> {
  return get<InboundRequestDetail>(`/inbound-requests/${requestId}`);
}
