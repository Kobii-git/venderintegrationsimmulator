import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../pages/DashboardPage";
import { DeliveryDetailPage } from "../pages/DeliveryDetailPage";
import { EventPreviewPage } from "../pages/EventPreviewPage";
import { SimulationFormPage } from "../pages/SimulationFormPage";
import { SimulationLivePage } from "../pages/SimulationLivePage";
import * as productsApi from "../api/products";
import * as simulationsApi from "../api/simulations";
import * as transportApi from "../api/transport";
import { ApiError } from "../api/client";
import type { ScenarioPreviewResponse } from "../types/api";

vi.mock("../api/simulations");
vi.mock("../api/products");
vi.mock("../api/transport");

const mockSimulation = {
  id: "sim-1",
  name: "UpGuard Test",
  product_id: "upguard",
  scenario_id: "data-leak",
  scenario_ids: ["data-leak"],
  simulation_mode: "push_webhook",
  fidelity_mode: "troubleshooting",
  status: "stopped" as const,
  destination: { url: "https://example.com/hook", method: "POST" },
  auth_config: {
    auth_method_id: "basic" as const,
    username: "hook-user",
    has_password: true,
    has_token: false,
  },
  scenario_overrides: {},
  schedule: { type: "manual" as const },
  fault_config: { enabled: false },
  inbound_config: { auth_method_id: "none" as const },
  random_seed: null,
  missing_secrets: [],
  runtime_stats: {
    events_generated: 2,
    events_attempted: 2,
    events_successful: 1,
    events_failed: 1,
    last_delivery_at: "2026-08-25T20:00:00Z",
    last_http_status: 200,
    last_latency_ms: 120,
    last_error_message: null,
    last_event_id: "evt-1",
    started_at: null,
    stopped_at: null,
    last_error_at: null,
    interrupted_on_restart: false,
  },
  created_at: "2026-08-25T19:00:00Z",
  updated_at: "2026-08-25T20:00:00Z",
};

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function scenarioPreview(
  scenarioId: string,
  correlationId: string,
  notificationType: string,
): ScenarioPreviewResponse {
  return {
    product_id: "upguard",
    scenario_id: scenarioId,
    scenario_display_name: scenarioId,
    scenario_description: null,
    correlation_id: correlationId,
    fidelity_mode: "troubleshooting",
    content_type: "application/json",
    method: "POST",
    payload: {
      notification: { type: notificationType },
      _simulator: { simulator_event_id: correlationId },
    },
  };
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(simulationsApi.listSimulations).mockResolvedValue([mockSimulation]);
  });

  it("loads and displays simulations", async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("UpGuard Test")).toBeInTheDocument();
    expect(screen.getByText("upguard")).toBeInTheDocument();
    expect(screen.getByText("stopped")).toBeInTheDocument();
  });
});

describe("SimulationFormPage", () => {
  beforeEach(() => {
    vi.mocked(productsApi.listProducts).mockResolvedValue([
      {
        id: "upguard",
        display_name: "UpGuard",
        version: "1.0.0",
        description: null,
        supported_modes: ["push_webhook"],
        supported_transports: ["http_webhook"],
        supported_auth_methods: ["none", "basic"],
        supported_inbound_auth_methods: ["none"],
        scenario_count: 2,
        has_plugin: true,
      },
    ]);
    vi.mocked(productsApi.getProduct).mockResolvedValue({
      ...mockSimulation,
      id: "upguard",
      display_name: "UpGuard",
      version: "1.0.0",
      description: null,
      supported_modes: ["push_webhook"],
      supported_transports: ["http_webhook"],
      supported_auth_methods: ["none", "basic"],
      supported_inbound_auth_methods: ["none"],
      scenario_count: 2,
      has_plugin: true,
      diagnostic_merge: "nested",
      scenarios: [
        {
          id: "data-leak",
          display_name: "Data Leak",
          description: null,
          default_transport: "http_webhook",
          config_schema: {},
        },
      ],
    } as never);
  });

  it("renders create form with product selection", async () => {
    render(
      <MemoryRouter>
        <SimulationFormPage />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText(/simulation name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/product/i)).toBeInTheDocument();
  });

  it("does not echo stored password on edit", async () => {
    vi.mocked(simulationsApi.getSimulation).mockResolvedValue(mockSimulation);
    vi.mocked(simulationsApi.updateSimulation).mockResolvedValue(mockSimulation);

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1/edit"]}>
        <Routes>
          <Route path="/simulations/:id/edit" element={<SimulationFormPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const password = await screen.findByLabelText(/^password$/i);
    expect(password).toHaveValue("");
    expect(password).toHaveAttribute("placeholder", "Leave blank to keep existing");

    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => {
      expect(simulationsApi.updateSimulation).toHaveBeenCalledWith(
        "sim-1",
        expect.not.objectContaining({ product_id: "upguard" }),
      );
    });
  });

  it("sends structured sensitivity metadata when testing a connection", async () => {
    vi.mocked(transportApi.testHttpConnection).mockResolvedValue({
      success: true,
      reached_server: true,
      started_at: "2026-08-26T00:00:00Z",
      completed_at: "2026-08-26T00:00:00Z",
      latency_ms: 12,
      destination: "https://collector.example/hook",
      method: "HEAD",
      request_headers_redacted: {},
      request_body: null,
      response_status_code: 200,
      response_headers_redacted: {},
      response_body: null,
      error_message: null,
      error_category: null,
    });
    render(
      <MemoryRouter>
        <SimulationFormPage />
      </MemoryRouter>,
    );

    await userEvent.type(
      await screen.findByLabelText(/webhook url/i),
      "https://collector.example/hook",
    );
    const addEntries = screen.getAllByRole("button", { name: /add entry/i });
    await userEvent.click(addEntries[0]);
    await userEvent.type(screen.getByLabelText("Custom headers name 1"), "X-Partner");
    await userEvent.type(screen.getByLabelText("Custom headers value 1"), "header-secret");
    await userEvent.click(addEntries[1]);
    await userEvent.type(
      screen.getByLabelText("URL query parameters name 1"),
      "partner",
    );
    await userEvent.type(
      screen.getByLabelText("URL query parameters value 1"),
      "query-secret",
    );
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    await waitFor(() => {
      expect(transportApi.testHttpConnection).toHaveBeenCalledWith(
        expect.objectContaining({
          sensitive_header_names: ["X-Partner"],
          sensitive_query_names: ["partner"],
        }),
      );
    });
  });

  it("renders vendor options from schema and includes them in the saved payload", async () => {
    vi.mocked(productsApi.listProducts).mockResolvedValue([
      {
        id: "okta",
        display_name: "Okta",
        version: "1.0.0",
        description: null,
        supported_modes: ["pull_api"],
        supported_transports: ["http_webhook"],
        supported_auth_methods: ["none"],
        supported_inbound_auth_methods: ["api_key"],
        scenario_count: 1,
        has_plugin: true,
      },
    ]);
    vi.mocked(productsApi.getProduct).mockResolvedValue({
      id: "okta",
      display_name: "Okta",
      version: "1.0.0",
      description: null,
      supported_modes: ["pull_api"],
      supported_transports: ["http_webhook"],
      supported_auth_methods: ["none"],
      supported_inbound_auth_methods: ["api_key"],
      scenario_count: 1,
      has_plugin: true,
      diagnostic_merge: "nested",
      inbound_options_schema: {
        type: "object",
        properties: {
          org_url: {
            type: "string",
            title: "Okta org URL",
            default: "https://example.okta.com",
          },
        },
        required: ["org_url"],
      },
      actions: [],
      scenarios: [
        {
          id: "user-session-start",
          display_name: "User Session Started",
          description: null,
          default_transport: "http_webhook",
          config_schema: {},
          supported_modes: ["pull_api"],
        },
      ],
    });
    vi.mocked(simulationsApi.createSimulation).mockResolvedValue({
      ...mockSimulation,
      product_id: "okta",
      scenario_id: "user-session-start",
      scenario_ids: ["user-session-start"],
      simulation_mode: "pull_api",
    });

    render(
      <MemoryRouter>
        <SimulationFormPage />
      </MemoryRouter>,
    );
    await userEvent.type(await screen.findByLabelText(/simulation name/i), "Okta polling");
    await userEvent.selectOptions(screen.getByLabelText(/product/i), "okta");
    expect(await screen.findByLabelText("Okta org URL")).toHaveValue(
      "https://example.okta.com",
    );
    await userEvent.click(screen.getByLabelText(/User Session Started/i));
    await userEvent.click(screen.getByRole("button", { name: /create simulation/i }));

    await waitFor(() => {
      expect(simulationsApi.createSimulation).toHaveBeenCalledWith(
        expect.objectContaining({
          inbound_config: expect.objectContaining({
            vendor_options: { org_url: "https://example.okta.com" },
          }),
        }),
      );
    });
  });
});

describe("SimulationLivePage", () => {
  beforeEach(() => {
    vi.mocked(productsApi.getProduct).mockResolvedValue({
      id: "upguard",
      display_name: "UpGuard",
      version: "1.0.0",
      description: null,
      supported_modes: ["push_webhook"],
      supported_transports: ["http_webhook"],
      supported_auth_methods: ["none", "basic"],
      supported_inbound_auth_methods: ["none"],
      scenario_count: 1,
      has_plugin: true,
      diagnostic_merge: "nested",
      actions: [],
      scenarios: [],
    });
    vi.mocked(simulationsApi.getSimulation).mockResolvedValue({
      ...mockSimulation,
      status: "running",
    });
    vi.mocked(simulationsApi.listSimulationEvents).mockResolvedValue([
      {
        id: "evt-1",
        simulation_id: "sim-1",
        product_id: "upguard",
        scenario_id: "data-leak",
        correlation_id: "corr-abc",
        status: "delivered",
        payload_source: "generated",
        generated_at: "2026-08-25T20:00:00Z",
        delivery_success: true,
        response_status_code: 200,
        latency_ms: 241,
      },
    ]);
  });

  it("shows counters and delivery rows", async () => {
    render(
      <MemoryRouter initialEntries={["/simulations/sim-1"]}>
        <Routes>
          <Route path="/simulations/:id" element={<SimulationLivePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Sent")).toBeInTheDocument();
    expect(screen.getByText("Successful")).toBeInTheDocument();
    expect(screen.getByText("corr-abc")).toBeInTheDocument();
    expect(screen.getAllByText("200").length).toBeGreaterThan(0);
  });

  it("calls start when start button clicked", async () => {
    vi.mocked(simulationsApi.getSimulation).mockResolvedValue({
      ...mockSimulation,
      status: "stopped",
      schedule: { type: "continuous", interval_seconds: 10 },
    });
    vi.mocked(simulationsApi.startSimulation).mockResolvedValue(mockSimulation);

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1"]}>
        <Routes>
          <Route path="/simulations/:id" element={<SimulationLivePage />} />
        </Routes>
      </MemoryRouter>,
    );

    const start = await screen.findByRole("button", { name: /start/i });
    await userEvent.click(start);

    await waitFor(() => {
      expect(simulationsApi.startSimulation).toHaveBeenCalledWith("sim-1");
    });
  });

  it("executes product workflow actions and shows the assertion result", async () => {
    vi.mocked(productsApi.getProduct).mockResolvedValue({
      id: "okta",
      display_name: "Okta",
      version: "1.0.0",
      description: null,
      supported_modes: ["push_webhook", "pull_api"],
      supported_transports: ["http_webhook"],
      supported_auth_methods: ["none"],
      supported_inbound_auth_methods: ["api_key"],
      scenario_count: 1,
      has_plugin: true,
      diagnostic_merge: "nested",
      scenarios: [],
      actions: [
        {
          id: "verify-event-hook",
          display_name: "Verify event-hook endpoint",
          supported_modes: ["push_webhook"],
        },
      ],
    });
    vi.mocked(simulationsApi.getSimulation).mockResolvedValue({
      ...mockSimulation,
      product_id: "okta",
      status: "stopped",
    });
    vi.mocked(simulationsApi.executeSimulationAction).mockResolvedValue({
      simulation_id: "sim-1",
      action_id: "verify-event-hook",
      event_id: "action-1",
      assertion_passed: true,
      delivery_success: true,
      response_status_code: 200,
      error_message: null,
    });

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1"]}>
        <Routes>
          <Route path="/simulations/:id" element={<SimulationLivePage />} />
        </Routes>
      </MemoryRouter>,
    );
    const verify = await screen.findByRole("button", {
      name: "Verify event-hook endpoint",
    });
    await userEvent.click(verify);
    await waitFor(() => {
      expect(simulationsApi.executeSimulationAction).toHaveBeenCalledWith(
        "sim-1",
        "verify-event-hook",
      );
    });
    expect(await screen.findByText(/verify-event-hook: verified/i)).toBeInTheDocument();
  });
});

describe("EventPreviewPage", () => {
  beforeEach(() => {
    vi.mocked(simulationsApi.getSimulation).mockReset();
    vi.mocked(simulationsApi.sendSimulationEvent).mockReset();
    vi.mocked(productsApi.previewScenario).mockReset();
  });

  it("sends the displayed preview correlation and edit state", async () => {
    vi.mocked(simulationsApi.getSimulation).mockResolvedValue(mockSimulation);
    vi.mocked(productsApi.previewScenario).mockResolvedValue({
      product_id: "upguard",
      scenario_id: "data-leak",
      scenario_display_name: "Data Leak",
      scenario_description: null,
      correlation_id: "preview-corr-123",
      fidelity_mode: "troubleshooting",
      content_type: "application/json",
      method: "POST",
      payload: {
        notification: { type: "DataLeakPublished" },
        _simulator: { simulator_event_id: "preview-corr-123" },
      },
    });
    vi.mocked(simulationsApi.sendSimulationEvent).mockResolvedValue({
      simulation_id: "sim-1",
      event_id: "evt-preview",
      correlation_id: "preview-corr-123",
      scenario_id: "data-leak",
      payload: { notification: { type: "DataLeakPublished" } },
      payload_source: "generated",
      delivery_success: true,
      response_status_code: 200,
      latency_ms: 12,
      error_message: null,
    });

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1/preview"]}>
        <Routes>
          <Route path="/simulations/:id/preview" element={<EventPreviewPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByDisplayValue("preview-corr-123")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send event" }));

    await waitFor(() => {
      expect(simulationsApi.sendSimulationEvent).toHaveBeenCalledWith("sim-1", {
        payload_override: {
          notification: { type: "DataLeakPublished" },
          _simulator: { simulator_event_id: "preview-corr-123" },
        },
        scenario_id: "data-leak",
        preview_correlation_id: "preview-corr-123",
        payload_edited: false,
      });
    });
  });

  it("never sends a stale preview when scenario requests resolve out of order", async () => {
    const staleVendorPreview = deferred<ScenarioPreviewResponse>();
    const latestDataLeakPreview = deferred<ScenarioPreviewResponse>();
    const initialPreview = scenarioPreview(
      "data-leak",
      "preview-corr-initial",
      "DataLeakPublished",
    );
    const latestPreview = scenarioPreview(
      "data-leak",
      "preview-corr-latest",
      "DataLeakUpdated",
    );
    const stalePreview = scenarioPreview(
      "vendor-risk",
      "preview-corr-stale",
      "VendorRiskChanged",
    );

    vi.mocked(simulationsApi.getSimulation).mockResolvedValue({
      ...mockSimulation,
      scenario_ids: ["data-leak", "vendor-risk"],
    });
    vi.mocked(productsApi.previewScenario)
      .mockResolvedValueOnce(initialPreview)
      .mockImplementationOnce(() => staleVendorPreview.promise)
      .mockImplementationOnce(() => latestDataLeakPreview.promise);
    vi.mocked(simulationsApi.sendSimulationEvent).mockResolvedValue({
      simulation_id: "sim-1",
      event_id: "evt-preview-latest",
      correlation_id: latestPreview.correlation_id,
      scenario_id: latestPreview.scenario_id,
      payload: latestPreview.payload,
      payload_source: "generated",
      delivery_success: true,
      response_status_code: 200,
      latency_ms: 12,
      error_message: null,
    });

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1/preview"]}>
        <Routes>
          <Route path="/simulations/:id/preview" element={<EventPreviewPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByDisplayValue(initialPreview.correlation_id)).toBeInTheDocument();
    const scenarioSelect = screen.getByLabelText("Scenario");
    const sendButton = screen.getByRole("button", { name: "Send event" });

    await userEvent.selectOptions(scenarioSelect, "vendor-risk");
    await waitFor(() => expect(productsApi.previewScenario).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Correlation ID")).toHaveValue("—");
    expect(sendButton).toBeDisabled();

    await userEvent.selectOptions(scenarioSelect, "data-leak");
    await waitFor(() => expect(productsApi.previewScenario).toHaveBeenCalledTimes(3));

    await act(async () => {
      latestDataLeakPreview.resolve(latestPreview);
    });
    expect(await screen.findByDisplayValue(latestPreview.correlation_id)).toBeInTheDocument();

    await act(async () => {
      staleVendorPreview.resolve(stalePreview);
    });
    expect(screen.getByLabelText("Correlation ID")).toHaveValue(latestPreview.correlation_id);

    await userEvent.click(sendButton);
    await waitFor(() => {
      expect(simulationsApi.sendSimulationEvent).toHaveBeenCalledWith("sim-1", {
        payload_override: latestPreview.payload,
        scenario_id: latestPreview.scenario_id,
        preview_correlation_id: latestPreview.correlation_id,
        payload_edited: false,
      });
    });
  });
});

describe("DeliveryDetailPage", () => {
  it("renders delivery attempt details with redacted headers", async () => {
    vi.mocked(simulationsApi.getSimulationEvent).mockResolvedValue({
      id: "evt-1",
      simulation_id: "sim-1",
      product_id: "upguard",
      scenario_id: "data-leak",
      correlation_id: "corr-abc",
      status: "delivered",
      payload_source: "generated",
      generated_at: "2026-08-25T20:00:00Z",
      delivery_success: true,
      response_status_code: 200,
      latency_ms: 241,
      fidelity_mode: "troubleshooting",
      replayed_from_event_id: null,
      simulator_metadata: {},
      payload: { notification: { type: "DataLeakPublished" } },
      delivery_attempts: [
        {
          id: "att-1",
          attempt_number: 1,
          started_at: "2026-08-25T20:00:00Z",
          completed_at: "2026-08-25T20:00:01Z",
          transport_id: "http_webhook",
          destination_summary: "https://example.com/hook",
          request_url_redacted: "https://example.com/hook",
          request_method: "POST",
          request_headers_redacted: { Authorization: "***REDACTED***" },
          request_query_params_redacted: {},
          request_body: '{"notification":{}}',
          response_status_code: 200,
          response_headers_redacted: {},
          response_body: '{"ok":true}',
          latency_ms: 241,
          success: true,
          error_message: null,
          error_category: null,
          error_explanation: null,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/simulations/sim-1/events/evt-1"]}>
        <Routes>
          <Route
            path="/simulations/:id/events/:eventId"
            element={<DeliveryDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("corr-abc")).toBeInTheDocument();
    expect(screen.getByText(/REDACTED/)).toBeInTheDocument();
    expect(screen.queryByText(/hook-secret/i)).not.toBeInTheDocument();
  });
});

describe("API error handling", () => {
  it("shows error when simulations fail to load", async () => {
    vi.mocked(simulationsApi.listSimulations).mockRejectedValue(
      new ApiError(422, "validation_error", "Invalid configuration"),
    );

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Invalid configuration")).toBeInTheDocument();
  });
});
