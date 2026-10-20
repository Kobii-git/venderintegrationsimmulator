import { expect, test } from "@playwright/test";

const receiverHost = process.env.E2E_RECEIVER_HOST ?? "receiver";

for (const transport of ["http", "udp"]) {
  test(`${transport} monitoring keeps history usable, pauses updates, and fits narrow screens`, async ({ page, request }) => {
    const created = await request.post("/api/v1/simulations", { data: {
      name: `Console tools ${transport}`, product_id: "fortinet", scenario_ids: ["forward-traffic-allow"],
      simulation_mode: "push_webhook", schedule: { type: "manual" },
      destination: transport === "udp"
        ? { transport_id: "syslog", host: receiverHost, port: 9514, protocol: "udp", format: "raw" }
        : { transport_id: "http_webhook", url: `http://${receiverHost}:9000/console-tools` },
    } });
    expect(created.status(), await created.text()).toBe(201);
    const id = (await created.json()).id;
    try {
      const sent = await request.post(`/api/v1/simulations/${id}/send`, { data: {} });
      expect(sent.ok(), await sent.text()).toBeTruthy();
      await page.goto(`/simulations/${id}`);
      await expect(page.getByRole("heading", { name: "Delivery overview" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Start", exact: true })).toHaveCount(0);
      await page.getByRole("tab", { name: "Overview", exact: true }).press("ArrowRight");
      await expect(page.getByRole("tab", { name: "Deliveries", exact: true })).toBeFocused();
      await expect(page).toHaveURL(/view=activity/);
      const history = page.getByRole("tabpanel", { name: "Deliveries", exact: true });
      await expect(history.locator("tbody tr")).toHaveCount(1);
      await expect(history.locator("tbody tr")).toContainText("success");
      if (transport === "http") await expect(history.locator("tbody tr")).toContainText("200");
      await page.getByRole("button", { name: "Pause live updates" }).click();
      let refreshes = 0;
      page.on("request", (req) => { if (new URL(req.url()).pathname === `/api/v1/simulations/${id}`) refreshes++; });
      await page.waitForTimeout(5300); // Cross the stopped simulation's five-second polling interval.
      expect(refreshes).toBe(0);
      await page.getByRole("button", { name: "Refresh now" }).click();
      await expect.poll(() => refreshes).toBe(1);

      let release!: () => void;
      const held = new Promise<void>((resolve) => { release = resolve; });
      await page.route(`**/simulations/${id}/events?**`, async (route) => {
        if (!new URL(route.request().url()).searchParams.has("success")) return route.continue();
        await held;
        await route.fulfill({ json: [] });
      });
      const staleRequest = page.waitForRequest((req) => req.url().includes("success=false"));
      await page.getByLabel("Outcome").selectOption("false");
      await staleRequest;
      const freshResponse = page.waitForResponse((res) => new URL(res.url()).pathname === `/api/v1/simulations/${id}/events` && !new URL(res.url()).searchParams.has("success"));
      await page.getByRole("button", { name: "Clear filters" }).click();
      await freshResponse;
      release();
      await expect(history.locator("tbody tr")).toHaveCount(1);
      await page.unroute(`**/simulations/${id}/events?**`);

      for (const width of [320, 390, 768, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      }
      await history.locator("tbody tr a").click();
      await expect(page.getByRole("heading", { name: "Delivery accepted", exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "Summary", exact: true }).press("ArrowRight");
      await expect(page.getByRole("heading", { name: "Request body", exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "Event payload", exact: true }).click();
      await expect(page.getByRole("tabpanel", { name: "Event payload", exact: true })).toContainText("_syslog_message");
      for (const width of [320, 768, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      }
      await page.getByRole("link", { name: "Back to simulation", exact: true }).click();
      await expect(page.getByRole("tab", { name: "Deliveries", exact: true })).toHaveAttribute("aria-selected", "true");
    } finally { await request.delete(`/api/v1/simulations/${id}`); }
  });
}
