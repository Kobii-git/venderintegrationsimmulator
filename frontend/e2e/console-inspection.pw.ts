import { expect, test, type Page } from "@playwright/test";

const receiverHost = process.env.E2E_RECEIVER_HOST ?? "receiver";
async function fits(page: Page) {
  for (const width of [320, 390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `page fits ${width}px`).toBe(true);
  }
}

test("guide reading retains filters, supports mobile section jumps and clipboard fallback", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", { value: { writeText: async () => { throw new Error("Unavailable"); } } });
  });
  await page.goto("/guides");
  await page.getByLabel("Vendor", { exact: true }).selectOption("cloudflare");
  await page.getByLabel("Search guides", { exact: true }).fill("Blob");
  await fits(page);
  await page.getByRole("link", { name: "Cloudflare: Azure Blob and Sentinel CCF", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await page.getByText("Documentation: complete — deployment verification", { exact: true }).click();
  await expect(page.getByRole("region", { name: "Deployment verification", exact: true })).toContainText("Not run");
  await fits(page);
  await page.getByRole("link", { name: "Production deployment", exact: true }).click();
  await page.getByRole("button", { name: "Copy command", exact: true }).first().click();
  await expect(page.getByText("Selected — copy with your keyboard", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.getSelection()?.toString())).toContain("az provider register");
  await page.setViewportSize({ width: 390, height: 900 });
  await page.getByLabel("Jump to section", { exact: true }).selectOption("troubleshooting");
  await expect(page).toHaveURL(/#troubleshooting$/);
  await expect(page.getByRole("heading", { name: "Troubleshooting", exact: true })).toBeInViewport();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Troubleshooting", exact: true })).toBeInViewport();
  await page.getByRole("link", { name: "Back to guide results", exact: true }).click();
  await expect(page.getByLabel("Search guides", { exact: true })).toHaveValue("Blob");
  await expect(page.getByLabel("Vendor", { exact: true })).toHaveValue("cloudflare");
  await page.getByRole("button", { name: "Clear filters", exact: true }).click();
  await expect(page.getByLabel("Vendor", { exact: true })).toHaveValue("");
});

test("event preview sends the visible payload, retains outcomes and records manual edits", async ({ page, request }) => {
  const created = await request.post("/api/v1/simulations", { data: {
    name: "Console preview browser", product_id: "upguard", scenario_ids: ["data-leak", "identity-breach"], simulation_mode: "push_webhook", schedule: { type: "manual" },
    destination: { transport_id: "http_webhook", url: `http://${receiverHost}:9000/console-preview` }, auth_config: { auth_method_id: "none" },
  } });
  expect(created.status(), await created.text()).toBe(201);
  const id = (await created.json()).id;
  try {
    let sends = 0;
    page.on("request", (req) => { if (req.method() === "POST" && req.url().endsWith(`/simulations/${id}/send`)) sends++; });
    await page.goto(`/simulations/${id}/preview`);
    await expect(page.getByRole("button", { name: "Send event", exact: true })).toBeEnabled();
    const original = JSON.parse(await page.getByLabel("Generated payload", { exact: true }).innerText());
    expect(sends).toBe(0);
    await page.getByLabel("Edit raw JSON for one-off send", { exact: true }).check();
    await page.getByLabel("Payload JSON", { exact: true }).fill("[]");
    await expect(page.getByRole("button", { name: "Send event", exact: true })).toBeDisabled();
    await expect(page.getByRole("alert")).toContainText("JSON object");
    await page.getByLabel("Payload JSON", { exact: true }).fill('{"message":"hidden draft"}');
    await fits(page);
    await page.getByLabel("Edit raw JSON for one-off send", { exact: true }).uncheck();
    const sending = page.waitForRequest((req) => req.method() === "POST" && req.url().endsWith(`/simulations/${id}/send`));
    await page.getByRole("button", { name: "Send event", exact: true }).click();
    expect((await sending).postDataJSON()).toMatchObject({ payload_override: original, payload_edited: false });
    await expect(page.getByRole("link", { name: "Inspect this delivery", exact: true })).toBeVisible();
    await page.waitForTimeout(1400); // Results must remain open rather than navigating after the former timeout.
    await expect(page).toHaveURL(new RegExp(`/simulations/${id}/preview$`));
    await page.getByLabel("Edit raw JSON for one-off send", { exact: true }).check();
    await page.getByLabel("Payload JSON", { exact: true }).fill('{"message":"phase-three-manual"}');
    await page.getByRole("button", { name: "Send again", exact: true }).click();
    await page.getByRole("link", { name: "Inspect this delivery", exact: true }).click();
    await page.getByRole("tab", { name: "Event payload", exact: true }).click();
    await expect(page.getByRole("tabpanel", { name: "Event payload", exact: true })).toContainText("phase-three-manual");
    const events = await (await request.get(`/api/v1/simulations/${id}/events`)).json();
    expect(events.some((event: { payload_source: string }) => event.payload_source === "manual_override")).toBe(true);
    const patched = await request.patch(`/api/v1/simulations/${id}`, { data: { destination: { transport_id: "http_webhook", url: `http://${receiverHost}:1/unavailable`, timeout_seconds: 1 } } });
    expect(patched.ok(), await patched.text()).toBeTruthy();
    await page.goto(`/simulations/${id}/preview`);
    await page.getByRole("button", { name: "Send event", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Delivery failed");
    await expect(page.getByRole("link", { name: "Inspect this delivery", exact: true })).toBeVisible();
    expect(await page.locator("body").innerText()).not.toContain("HTTP null");
  } finally { await request.delete(`/api/v1/simulations/${id}`); }
});

test("request explorer filters named simulations and opens redacted authentication evidence", async ({ page, request }) => {
  const created = await request.post("/api/v1/simulations", { data: {
    name: "Console inbound browser", product_id: "demo-pull", scenario_ids: ["security-event"], simulation_mode: "pull_api", schedule: { type: "manual" }, destination: { transport_id: "http_webhook" },
    auth_config: { auth_method_id: "none", oauth_client_id: "phase-three-client", oauth_client_secret: "phase-three-client-canary" },
    inbound_config: { auth_method_id: "oauth2_client_credentials", dataset_size: 3 },
  } });
  expect(created.status(), await created.text()).toBe(201);
  const id = (await created.json()).id;
  try {
    expect((await request.post(`/api/v1/simulations/${id}/start`)).ok()).toBeTruthy();
    const token = await request.post(`/api/v1/oauth2/token?simulation_id=${id}`, { form: { grant_type: "client_credentials", client_id: "phase-three-client", client_secret: "phase-three-client-canary" } });
    expect(token.status()).toBe(200);
    const apiPath = `/api/v1/mock/demo-pull/events?simulation_id=${id}&limit=2`;
    expect((await request.get(apiPath, { headers: { Authorization: "Bearer phase-three-invalid-canary" } })).status()).toBe(401);
    expect((await request.get(apiPath, { headers: { Authorization: `Bearer ${(await token.json()).access_token}` } })).status()).toBe(200);
    await page.goto(`/inbound-requests?simulation=${id}`);
    await expect(page.getByLabel("Simulation", { exact: true })).toHaveValue(id);
    await expect(page.getByRole("option", { name: "Console inbound browser", exact: true })).toBeAttached();
    await expect(page.getByRole("region", { name: "Scrollable request history", exact: true }).locator("tbody tr")).toHaveCount(3);
    await fits(page);
    await page.getByLabel("Response status", { exact: true }).fill("401");
    await page.getByLabel("Kind", { exact: true }).selectOption("api");
    await page.getByRole("button", { name: "Apply filters", exact: true }).click();
    await expect(page.getByRole("region", { name: "Scrollable request history", exact: true }).locator("tbody tr")).toHaveCount(1);
    await page.getByLabel("Search recent requests", { exact: true }).fill("events");
    const link = page.getByRole("region", { name: "Scrollable request history", exact: true }).locator("tbody tr a");
    await link.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: /Request failed/ })).toBeVisible();
    await page.getByRole("tab", { name: "Summary", exact: true }).press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Request", exact: true })).toBeFocused();
    await expect(page.getByLabel("Recorded request headers", { exact: true })).toContainText(/redact/i);
    expect(await page.locator("body").innerText()).not.toContain("phase-three-invalid-canary");
    await page.getByRole("tab", { name: "Request", exact: true }).press("ArrowRight");
    await expect(page.getByRole("heading", { name: "Response headers", exact: true })).toBeVisible();
    await expect(page.getByLabel("Recorded response body", { exact: true })).toContainText(/error/);
    await fits(page);
    await page.getByRole("link", { name: "Back to all requests", exact: true }).click();
    await expect(page.getByLabel("Simulation", { exact: true })).toHaveValue(id);
    await expect(page.getByLabel("Response status", { exact: true })).toHaveValue("401");
    await expect(page.getByLabel("Search recent requests", { exact: true })).toHaveValue("events");
  } finally { await request.post(`/api/v1/simulations/${id}/stop`); await request.delete(`/api/v1/simulations/${id}`); }
});
