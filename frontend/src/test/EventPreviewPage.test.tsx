import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { previewScenario } from "../api/products";
import { getSimulation, sendSimulationEvent } from "../api/simulations";
import { EventPreviewPage } from "../pages/EventPreviewPage";
import type { ScenarioPreviewResponse, SimulationResponse, SimulationSendResponse } from "../types/api";

vi.mock("../api/products", () => ({ previewScenario: vi.fn() }));
vi.mock("../api/simulations", () => ({ getSimulation: vi.fn(), sendSimulationEvent: vi.fn() }));
const simulation = { id: "sim-1", name: "Preview test", product_id: "demo", scenario_id: "first", scenario_ids: ["first", "second"], scenario_overrides: {}, fidelity_mode: "vendor_accurate", simulation_mode: "push_webhook", missing_secrets: [], destination: { transport_id: "http_webhook", url: "https://collector.example/hook?secret=hidden" } } as unknown as SimulationResponse;
const sample: ScenarioPreviewResponse = { product_id: "demo", scenario_id: "first", scenario_display_name: "First", scenario_description: "Example event", correlation_id: "correlation-1", fidelity_mode: "vendor_accurate", content_type: "application/json", method: "POST", payload: { message: "generated" } };
const sent = { event_id: "event-1", delivery_success: true, scenario_id: "first", response_status_code: 200, latency_ms: 1 } as SimulationSendResponse;
beforeEach(() => {
  vi.resetAllMocks(); vi.mocked(getSimulation).mockResolvedValue(simulation); vi.mocked(previewScenario).mockResolvedValue(sample); vi.mocked(sendSimulationEvent).mockResolvedValue(sent);
});
function open() { render(<MemoryRouter initialEntries={["/simulations/sim-1/preview"]}><Routes><Route path="/simulations/:id/preview" element={<EventPreviewPage />} /></Routes></MemoryRouter>); }
async function ready() { open(); await waitFor(() => expect(screen.getByRole("button", { name: "Send event" })).toBeEnabled()); }

it("previews without sending and summarizes destinations without query credentials", async () => {
  await ready();
  expect(sendSimulationEvent).not.toHaveBeenCalled();
  expect(screen.getByText("https://collector.example/hook")).toBeInTheDocument();
  expect(screen.queryByText(/secret=hidden/)).not.toBeInTheDocument();
});
it("sends the generated payload when editing is turned off, even if a draft differs", async () => {
  const user = userEvent.setup(); await ready();
  await user.click(screen.getByLabelText("Edit raw JSON for one-off send"));
  await user.clear(screen.getByLabelText("Payload JSON")); await user.paste('{"message":"edited"}');
  await user.click(screen.getByLabelText("Edit raw JSON for one-off send"));
  await user.click(screen.getByRole("button", { name: "Send event" }));
  expect(sendSimulationEvent).toHaveBeenCalledWith("sim-1", { payload_override: sample.payload, scenario_id: "first", preview_correlation_id: "correlation-1", payload_edited: false });
  expect(await screen.findByRole("link", { name: "Inspect this delivery" })).toHaveAttribute("href", "/simulations/sim-1/events/event-1");
});
it("blocks invalid JSON objects and resets edits before a one-off send", async () => {
  const user = userEvent.setup(); await ready(); await user.click(screen.getByLabelText("Edit raw JSON for one-off send"));
  for (const invalid of ["{", "[]", "null", '"text"', "12"]) {
    await user.clear(screen.getByLabelText("Payload JSON")); await user.paste(invalid);
    expect(screen.getByRole("button", { name: "Send event" })).toBeDisabled();
    expect(screen.getByLabelText("Payload JSON")).toHaveAttribute("aria-invalid", "true");
  }
  await user.click(screen.getByRole("button", { name: "Reset edits" }));
  await user.click(screen.getByRole("button", { name: "Send event" }));
  expect(sendSimulationEvent).toHaveBeenCalledWith("sim-1", expect.objectContaining({ payload_override: sample.payload, payload_edited: true }));
});
it("blocks sending without required saved credentials", async () => {
  vi.mocked(getSimulation).mockResolvedValue({ ...simulation, missing_secrets: ["token"] }); open();
  expect(await screen.findByText(/Add these credentials/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send event" })).toBeDisabled();
});
it("ignores a late preview after switching scenarios", async () => {
  let resolve!: (value: ScenarioPreviewResponse) => void;
  vi.mocked(previewScenario).mockImplementationOnce(() => new Promise((done) => { resolve = done; })).mockResolvedValueOnce({ ...sample, scenario_id: "second", payload: { message: "second" } });
  const user = userEvent.setup(); open(); await screen.findByLabelText("Scenario");
  await user.selectOptions(screen.getByLabelText("Scenario"), "second");
  await waitFor(() => expect(screen.getByRole("button", { name: "Send event" })).toBeEnabled());
  await act(async () => resolve(sample));
  expect(screen.getByLabelText("Generated payload")).toHaveTextContent("second");
  await user.click(screen.getByRole("button", { name: "Send event" }));
  expect(sendSimulationEvent).toHaveBeenCalledWith("sim-1", expect.objectContaining({ scenario_id: "second", payload_override: { message: "second" } }));
});
it("keeps failed delivery evidence on the preview and prevents a double submission", async () => {
  let resolve!: (value: SimulationSendResponse) => void;
  vi.mocked(sendSimulationEvent).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
  const user = userEvent.setup(); await ready(); await user.dblClick(screen.getByRole("button", { name: "Send event" }));
  expect(sendSimulationEvent).toHaveBeenCalledTimes(1);
  await act(async () => resolve({ ...sent, delivery_success: false, error_message: "Collector rejected the event" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Collector rejected");
  expect(screen.getByRole("link", { name: "Inspect this delivery" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send again" })).toBeEnabled();
});
it("recovers from a simulation load error without losing the return path", async () => {
  vi.mocked(getSimulation).mockRejectedValueOnce(new Error("Preview unavailable"));
  const user = userEvent.setup(); open();
  expect(await screen.findByRole("alert")).toHaveTextContent("Preview unavailable");
  expect(screen.getByRole("link", { name: "Back to live view" })).toHaveAttribute("href", "/simulations/sim-1");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Send event" })).toBeEnabled());
});
