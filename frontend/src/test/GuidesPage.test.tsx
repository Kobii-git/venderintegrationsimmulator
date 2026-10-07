import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { get } from "../api/client";
import { GuidesPage } from "../pages/GuidesPage";

vi.mock("../api/client", () => ({ get: vi.fn() }));
const guide = { product_id: "cloudflare", product_name: "Cloudflare", method_id: "native", title: "Cloudflare HTTP Logpush", summary: "Compression and delivery", connection_methods: ["HTTP Logpush"], destinations: ["Microsoft Sentinel"], support: "native simulation", reviewed_at: "2026-10-07", content: "# Cloudflare\n\n## Production deployment\n\n```bash\ncurl --fail https://example.test\n```\n\n<script>window.bad=true</script>\n\n[Unsafe](javascript:alert(1))\n\n## Simulator testing\n\nGenerate a raw log." };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(get).mockImplementation(async path => path === "/guides" ? [guide] : guide); });
function show(path: string) { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/guides" element={<GuidesPage />} /><Route path="/guides/:productId/:methodId" element={<GuidesPage />} /></Routes></MemoryRouter>); }
it("filters guides by vendor, method, destination and search", async () => {
 const user = userEvent.setup(); show("/guides");
 expect(await screen.findByRole("link", { name: guide.title })).toBeInTheDocument();
 await user.selectOptions(screen.getByLabelText("Vendor"), "cloudflare");
 await user.selectOptions(screen.getByLabelText("Connection method"), "HTTP Logpush");
 await user.selectOptions(screen.getByLabelText("Destination"), "Microsoft Sentinel");
 await user.type(screen.getByLabelText("Search guides"), "unknown vendor");
 expect(screen.getByText("No guides match these filters.")).toBeInTheDocument();
 await user.clear(screen.getByLabelText("Search guides"));
 expect(screen.getByRole("link", { name: guide.title })).toBeInTheDocument();
});
it("renders safe Markdown, contents and copyable commands with raw generation links", async () => {
 const user = userEvent.setup(); const { container } = show("/guides/cloudflare/native");
 expect(await screen.findByRole("heading", { name: "Production deployment" })).toHaveAttribute("id", "production-deployment");
 expect(screen.getByRole("link", { name: "Production deployment" })).toHaveAttribute("href", "#production-deployment");
 expect(container.querySelector("script")).toBeNull();
 expect(screen.getByText("Unsafe")).not.toHaveAttribute("href", "javascript:alert(1)");
 await user.click(screen.getByRole("button", { name: "Copy command" }));
 expect(await navigator.clipboard.readText()).toContain("curl --fail https://example.test");
 expect(screen.getByRole("link", { name: "Generate raw log" })).toHaveAttribute("href", "/raw-logs?product=cloudflare");
 expect(screen.getByRole("button", { name: "Download Markdown" })).toBeEnabled();
 expect(screen.getByRole("button", { name: "Print guide" })).toBeEnabled();
});
