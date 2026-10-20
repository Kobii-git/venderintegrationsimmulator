import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/simulations";
import { InboundRequestsPage } from "../pages/InboundRequestsPage";
import { InboundRequestDetailPage } from "../pages/InboundRequestDetailPage";
import type { InboundRequestDetail, SimulationResponse } from "../types/api";
vi.mock("../api/simulations", () => ({ listAllInboundRequests: vi.fn(), listSimulations: vi.fn(), getAnyInboundRequest: vi.fn(), getInboundRequest: vi.fn() }));
const entry: InboundRequestDetail = { id: "request-1", simulation_id: "sim-1", product_id: "demo-pull", route_id: "events", received_at: "2026-10-20T19:00:00Z", request_method: "GET", request_path: "/mock/events", response_status_code: 401, auth_method_id: "bearer", auth_result: "failed", latency_ms: 2, items_returned: 0, error_message: "Invalid bearer token", request_kind: "api", request_query_params: { limit: "3" }, request_headers_redacted: { authorization: "[REDACTED]" }, request_body: null, response_headers: { "content-type": "text/plain" }, response_body: "Token expired\nTry a new token." };
beforeEach(() => {
 vi.resetAllMocks(); vi.mocked(api.listAllInboundRequests).mockResolvedValue([entry]); vi.mocked(api.listSimulations).mockResolvedValue([{ id: "sim-1", name: "Collector demo" } as SimulationResponse]); vi.mocked(api.getAnyInboundRequest).mockResolvedValue(entry); vi.mocked(api.getInboundRequest).mockResolvedValue(entry);
});
function open(path = "/inbound-requests") { render(<MemoryRouter initialEntries={[path]}><Link to="/inbound-requests/request-2">Next request</Link><Routes><Route path="/inbound-requests" element={<InboundRequestsPage />} /><Route path="/inbound-requests/:requestId" element={<InboundRequestDetailPage />} /></Routes></MemoryRouter>); }
it("uses simulation names, applies explicit filters and retains context when inspecting", async () => {
 const user = userEvent.setup(); open(); await screen.findByRole("option", { name: "Collector demo" });
 await user.selectOptions(screen.getByLabelText("Simulation"), "sim-1"); await user.type(screen.getByLabelText("Response status"), "401");
 expect(api.listAllInboundRequests).toHaveBeenCalledTimes(1);
 await user.click(screen.getByRole("button", { name: "Apply filters" }));
 await waitFor(() => expect(api.listAllInboundRequests).toHaveBeenLastCalledWith({ limit: 100, simulation_id: "sim-1", request_kind: undefined, response_status: 401 }));
 await user.type(screen.getByLabelText("Search recent requests"), "expired");
 expect(screen.getByText("No matching requests")).toBeInTheDocument();
 await user.clear(screen.getByLabelText("Search recent requests"));
 const time = screen.getByRole("link", { name: /2026/ }); await user.click(time);
 expect(await screen.findByRole("link", { name: "Back to all requests" })).toHaveAttribute("href", "/inbound-requests?simulation=sim-1&status=401");
});
it("rejects an invalid URL status without fetching misleading history", async () => {
 open("/inbound-requests?status=99");
 expect(await screen.findByRole("alert")).toHaveTextContent("100 to 599"); expect(api.listAllInboundRequests).not.toHaveBeenCalled();
});
it("ignores a late filter response after clearing filters", async () => {
 let resolve!: (value: InboundRequestDetail[]) => void;
 vi.mocked(api.listAllInboundRequests).mockResolvedValueOnce([entry]).mockImplementationOnce(() => new Promise((done) => { resolve = done; })).mockResolvedValueOnce([entry]);
 const user = userEvent.setup(); open(); await screen.findByRole("option", { name: "Collector demo" });
 await user.selectOptions(screen.getByLabelText("Kind"), "token"); await user.click(screen.getByRole("button", { name: "Apply filters" }));
 await user.click(screen.getByRole("button", { name: "Clear filters" }));
 await screen.findByRole("link", { name: /2026/ }); await act(async () => resolve([]));
 expect(screen.getByRole("link", { name: /2026/ })).toBeInTheDocument();
});
it("keeps audit evidence usable if simulation names cannot be loaded", async () => {
 vi.mocked(api.listSimulations).mockRejectedValueOnce(new Error("Unavailable")); open();
 expect(await screen.findByText("Saved simulation")).toBeInTheDocument(); expect(screen.getByText("sim-1")).toBeInTheDocument();
});
it("switches evidence tabs with the keyboard and preserves plain response text on copy", async () => {
 const user = userEvent.setup(); open("/inbound-requests/request-1?kind=api");
 expect(await screen.findByRole("heading", { name: /Request failed/ })).toBeInTheDocument();
 await user.click(screen.getByRole("tab", { name: "Summary" })); await user.keyboard("{ArrowRight}");
 expect(screen.getByRole("tab", { name: "Request" })).toHaveFocus();
 expect(screen.getByLabelText("Recorded request headers")).toHaveTextContent("[REDACTED]");
 await user.keyboard("{ArrowRight}"); expect(screen.getByRole("tab", { name: "Response" })).toHaveFocus();
 expect(screen.getByLabelText("Recorded response body").textContent).toBe(entry.response_body);
 await user.click(screen.getByRole("button", { name: "Copy body" })); expect(await navigator.clipboard.readText()).toBe(entry.response_body);
});
it("never displays old request details when a new request fails to load", async () => {
 vi.mocked(api.getAnyInboundRequest).mockResolvedValueOnce(entry).mockRejectedValueOnce(new Error("Request no longer available"));
 const user = userEvent.setup(); open("/inbound-requests/request-1"); await screen.findByRole("heading", { name: "Request summary" }); await user.click(screen.getByRole("link", { name: "Next request" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("Request no longer available"); expect(screen.queryByText(entry.request_path)).not.toBeInTheDocument();
});
