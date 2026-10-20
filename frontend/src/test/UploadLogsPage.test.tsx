import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import * as client from "../api/client";
import * as api from "../api/simulations";
import { UploadLogsPage } from "../pages/UploadLogsPage";
import type { SimulationResponse } from "../types/api";

vi.mock("../api/client", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api/client")>(),
  get: vi.fn(), post: vi.fn(), request: vi.fn(),
}));
vi.mock("../api/simulations", () => ({ createSimulation: vi.fn(), getSimulation: vi.fn(), startSimulation: vi.fn(), stopSimulation: vi.fn() }));
const dataset = { id: "dataset-1", name: "example.ndjson", record_count: 2 };
const validation = { record_count: 2, records: [{ message: "sample" }], payload_mode: "envelope", schema_verified: false };
const saved = {
  id: "upload-1", name: "Upload", status: "stopped", targets: [{ stats: { queued: 0 } }],
  runtime_stats: { events_generated: 0, events_successful: 0, events_failed: 0 },
} as unknown as SimulationResponse;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.get).mockResolvedValue([dataset]);
  vi.mocked(client.post).mockResolvedValue(validation);
  vi.mocked(api.createSimulation).mockResolvedValue(saved);
  vi.mocked(api.getSimulation).mockResolvedValue(saved);
  vi.mocked(api.startSimulation).mockResolvedValue({ ...saved, status: "completed" });
});
function open() { render(<MemoryRouter><UploadLogsPage /></MemoryRouter>); }
async function review() {
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "example.ndjson (2 records)" });
  await user.selectOptions(screen.getByLabelText("Dataset"), dataset.id);
  await user.click(screen.getByRole("button", { name: "Validate and preview" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.selectOptions(screen.getByLabelText("Delivery path"), "azure_function_app");
  await user.type(screen.getByLabelText("Function ingestion URL"), "https://relay.example/ingest?sig=hidden-query");
  await user.type(screen.getByLabelText("Function key"), "hidden-key");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  return user;
}

it("requires a validated preview, clears it when the payload changes, and retains selections on Back", async () => {
  open(); const user = userEvent.setup();
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  await screen.findByRole("option", { name: "example.ndjson (2 records)" });
  await user.selectOptions(screen.getByLabelText("Dataset"), dataset.id);
  await user.click(screen.getByRole("button", { name: "Validate and preview" }));
  expect(await screen.findByLabelText("Ingestion preview")).toHaveTextContent("sample");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByRole("heading", { name: "Destination" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Back" }));
  expect(screen.getByLabelText("Dataset")).toHaveValue(dataset.id);
  await user.selectOptions(screen.getByLabelText("Payload mode"), "json");
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  expect(screen.queryByLabelText("Ingestion preview")).not.toBeInTheDocument();
});

it("reviews endpoint and records without exposing secrets or starting delivery", async () => {
  open(); await review();
  expect(screen.getByRole("heading", { name: "Review & send" })).toBeInTheDocument();
  expect(screen.getByText("https://relay.example/ingest")).toBeInTheDocument();
  expect(screen.queryByText(/hidden-query|hidden-key/)).not.toBeInTheDocument();
  expect(api.createSimulation).not.toHaveBeenCalled(); expect(api.startSimulation).not.toHaveBeenCalled();
});

it("retries a failed Start on the saved run without creating another simulation", async () => {
  vi.mocked(api.startSimulation).mockRejectedValueOnce(new Error("Start unavailable"));
  open(); const user = await review();
  await user.click(screen.getByRole("button", { name: "Upload to Azure" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Start unavailable");
  expect(api.createSimulation).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Start saved upload" }));
  await waitFor(() => expect(api.startSimulation).toHaveBeenCalledTimes(2));
  expect(api.createSimulation).toHaveBeenCalledTimes(1);
  expect(api.startSimulation).toHaveBeenLastCalledWith("upload-1");
});

it("keeps new uploads disabled while a stopped run still has queued records", async () => {
  vi.mocked(api.startSimulation).mockResolvedValue({ ...saved, targets: [{ ...saved.targets![0], stats: { queued: 1 } }] });
  open(); const user = await review();
  await user.click(screen.getByRole("button", { name: "Upload to Azure" }));
  expect(await screen.findByRole("button", { name: "Start another upload" })).toBeDisabled();
  expect(screen.getByText(/Queued records may continue draining/)).toBeInTheDocument();
});
