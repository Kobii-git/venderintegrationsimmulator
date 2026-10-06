import { Buffer } from "node:buffer";

import { expect, test, type APIRequestContext } from "@playwright/test";

const apiPath = "/api/v1";
const receiverHost = process.env.E2E_RECEIVER_HOST ?? "receiver";
const runId = Date.now().toString(36);
let upguardId = "";
let fortinetId = "";
let pullId = "";
let oauthId = "";
let sophosId = "";
let oktaPullId = "";
let oktaHookId = "";

const sophosTenantId = "57ca9a6b-885f-4e36-95ec-290548c26059";
const sophosClientSecret = `sophos-browser-secret-${runId}`;
const oktaApiToken = `okta-browser-token-${runId}`;

async function createSimulation(
  request: APIRequestContext,
  payload: Record<string, unknown>,
): Promise<string> {
  const response = await request.post(`${apiPath}/simulations`, { data: payload });
  expect(response.status(), await response.text()).toBe(201);
  return String((await response.json()).id);
}

function common(name: string, productId: string, scenarioId: string) {
  return {
    name: `${name} ${runId}`,
    product_id: productId,
    scenario_id: scenarioId,
    scenario_ids: [scenarioId],
    fidelity_mode: "troubleshooting",
    scenario_overrides: {},
    schedule: { type: "manual" },
  };
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  upguardId = await createSimulation(request, {
    ...common("E2E UpGuard", "upguard", "data-leak"),
    scenario_ids: ["data-leak", "identity-breach"],
    simulation_mode: "push_webhook",
    destination: {
      transport_id: "http_webhook",
      url: `http://${receiverHost}:9000/e2e-upguard`,
      method: "POST",
      headers: [
        { name: "X-E2E-Key", value: `browser-canary-${runId}`, sensitive: true },
      ],
    },
    auth_config: {
      auth_method_id: "basic",
      username: "browser-operator",
      password: `browser-password-${runId}`,
    },
  });

  fortinetId = await createSimulation(request, {
    ...common("E2E Fortinet", "fortinet", "forward-traffic-allow"),
    simulation_mode: "push_webhook",
    fidelity_mode: "vendor_accurate",
    destination: {
      transport_id: "syslog",
      host: receiverHost,
      port: 9514,
      protocol: "udp",
      format: "raw",
    },
    auth_config: { auth_method_id: "none" },
  });

  pullId = await createSimulation(request, {
    ...common("E2E Pull", "demo-pull", "security-event"),
    simulation_mode: "pull_api",
    destination: { transport_id: "http_webhook" },
    auth_config: { auth_method_id: "none" },
    inbound_config: {
      auth_method_id: "none",
      dataset_size: 4,
      item_interval_seconds: 30,
    },
  });

  oauthId = await createSimulation(request, {
    ...common("E2E OAuth", "demo-pull", "security-event"),
    simulation_mode: "pull_api",
    destination: { transport_id: "http_webhook" },
    auth_config: {
      auth_method_id: "none",
      oauth_client_id: `browser-client-${runId}`,
      oauth_client_secret: `browser-oauth-secret-${runId}`,
    },
    inbound_config: {
      auth_method_id: "oauth2_client_credentials",
      dataset_size: 3,
      oauth_token_ttl_seconds: 600,
      oauth_allowed_scopes: ["events.read"],
    },
  });

  sophosId = await createSimulation(request, {
    ...common("E2E Sophos", "sophos-central", "core-malware-detection"),
    scenario_ids: [
      "core-malware-detection",
      "behavioral-detection",
      "pua-detection",
      "ips-inbound-detection",
      "ips-outbound-detection",
    ],
    simulation_mode: "pull_api",
    auth_config: {
      oauth_client_id: `sophos-browser-client-${runId}`,
      oauth_client_secret: sophosClientSecret,
    },
    inbound_config: {
      auth_method_id: "oauth2_client_credentials",
      oauth_allowed_scopes: ["token"],
      dataset_size: 205,
      vendor_options: { tenant_id: sophosTenantId },
    },
  });

  oktaPullId = await createSimulation(request, {
    ...common("E2E Okta Pull", "okta", "user-session-start"),
    scenario_ids: [
      "user-session-start",
      "user-lifecycle-create",
      "user-lifecycle-deactivate",
      "application-membership-add",
      "user-authentication-sso",
      "application-sign-on-denied",
    ],
    simulation_mode: "pull_api",
    auth_config: { auth_method_id: "bearer", token: oktaApiToken },
    inbound_config: {
      auth_method_id: "api_key",
      api_key_header: "Authorization",
      api_key_prefix: "SSWS ",
      dataset_size: 5,
      vendor_options: { org_url: "https://example.okta.com" },
    },
  });

  oktaHookId = await createSimulation(request, {
    ...common("E2E Okta Hook", "okta", "user-session-start"),
    simulation_mode: "push_webhook",
    destination: {
      transport_id: "http_webhook",
      url: `http://${receiverHost}:9000/okta-verify`,
      method: "POST",
    },
    auth_config: { auth_method_id: "none" },
    inbound_config: { vendor_options: { org_url: "https://example.okta.com" } },
  });
});

test("UpGuard preview/send, fault, attempt, cURL, replay, export, and import", async ({
  page,
  request,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(`/simulations/${upguardId}/preview`);
  await expect(page.getByRole("heading", { name: "Event Preview" })).toBeVisible();
  await page.getByLabel("Scenario").selectOption("identity-breach");
  await expect(page.locator(".json-viewer")).toContainText("IdentityBreachPublished");
  const previewCorrelationId = await page.getByLabel("Correlation ID").inputValue();
  await page.getByRole("button", { name: "Send event" }).click();
  await expect(page.getByText(/Delivered previewed identity-breach payload/)).toBeVisible();

  const eventsResponse = await request.get(`${apiPath}/simulations/${upguardId}/events`);
  const events = (await eventsResponse.json()) as Array<{
    id: string;
    correlation_id: string;
    payload_source: string;
  }>;
  expect(events).toHaveLength(1);
  expect(events[0].correlation_id).toBe(previewCorrelationId);
  expect(events[0].payload_source).toBe("generated");
  const eventResponse = await request.get(
    `${apiPath}/simulations/${upguardId}/events/${events[0].id}`,
  );
  const event = (await eventResponse.json()) as {
    correlation_id: string;
    payload_source: string;
    simulator_metadata: Record<string, unknown>;
    delivery_attempts: Array<{ error_category: string | null }>;
  };
  expect(event.correlation_id).toBe(previewCorrelationId);
  expect(event.payload_source).toBe("generated");
  expect(event.simulator_metadata).toMatchObject({ preview_send: true });
  expect(event.delivery_attempts[0].error_category).toBeNull();
  await page.goto(`/simulations/${upguardId}/events/${events[0].id}`);
  await expect(page.getByRole("heading", { name: "Delivery attempts" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Selected" })).toBeVisible();
  await page.getByRole("button", { name: "Copy as cURL" }).click();
  await expect(page.getByText(/cURL for attempt .* copied/)).toBeVisible();
  await page.getByRole("button", { name: "Replay exact payload" }).click();
  await expect(page.getByText(/Exact payload replayed/)).toBeVisible();

  const patch = await request.patch(`${apiPath}/simulations/${upguardId}`, {
    data: {
      fault_config: {
        enabled: true,
        payload: { remove_fields: ["notification.occurredAt"] },
        delivery: { retry_count: 1, retry_delay_ms: 10 },
      },
    },
  });
  expect(patch.ok(), await patch.text()).toBeTruthy();
  await page.goto(`/simulations/${upguardId}`);
  await expect(page.getByText(/Fault injection is ENABLED/)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export config" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("e2e-upguard");

  const exportedResponse = await request.get(`${apiPath}/simulations/${upguardId}/export`);
  const exported = (await exportedResponse.json()) as Record<string, unknown>;
  expect(JSON.stringify(exported)).not.toContain(`browser-password-${runId}`);
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({
    name: "sanitized-simulation.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(exported)),
  });
  await expect(page.getByText(/Start\/Send is blocked until/)).toBeVisible();
});

test("Fortinet syslog is operable and remains vendor accurate", async ({ page, request }) => {
  await page.goto(`/simulations/${fortinetId}`);
  await page.getByRole("button", { name: "Send one now" }).click();
  await expect(page.getByText("Successful").locator("..")).toContainText("1");
  const events = await request.get(`${apiPath}/simulations/${fortinetId}/events`);
  const event = ((await events.json()) as Array<{ id: string }>)[0];
  const detail = await request.get(`${apiPath}/simulations/${fortinetId}/events/${event.id}`);
  expect(JSON.stringify((await detail.json()).payload)).not.toContain("simulator_event_id");
});

test("pull dataset pagination and global inbound audit are visible", async ({ page, request }) => {
  await page.goto(`/simulations/${pullId}`);
  await expect(page.getByRole("button", { name: "Send one now" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Preview event" })).toHaveCount(0);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText("Dataset items").locator("..")).toContainText("8");

  const first = await request.get(
    `${apiPath}/mock/demo-pull/events?simulation_id=${pullId}&limit=3`,
  );
  expect(first.ok(), await first.text()).toBeTruthy();
  const firstPage = (await first.json()) as {
    events: unknown[];
    nextPageToken: string;
  };
  expect(firstPage.events).toHaveLength(3);
  const terminal = await request.get(`${apiPath}/mock/demo-pull/events`, {
    params: {
      simulation_id: pullId,
      limit: 3,
      pageToken: firstPage.nextPageToken,
    },
  });
  const terminalPage = (await terminal.json()) as {
    events: unknown[];
    nextPageToken?: string;
  };
  expect(terminalPage.events).toHaveLength(1);
  expect(terminalPage.nextPageToken).toBeUndefined();

  await page.goto("/inbound-requests");
  await expect(page.getByRole("heading", { name: "Inbound Requests" })).toBeVisible();
  await expect(page.getByText(`${pullId}`).first()).toBeVisible();
});

test("OAuth token metadata is visible without token prefixes", async ({ page, request }) => {
  expect((await request.post(`${apiPath}/simulations/${oauthId}/start`)).ok()).toBeTruthy();
  const token = await request.post(`${apiPath}/oauth2/token`, {
    params: { simulation_id: oauthId },
    form: {
      grant_type: "client_credentials",
      client_id: `browser-client-${runId}`,
      client_secret: `browser-oauth-secret-${runId}`,
      scope: "events.read",
    },
  });
  expect(token.ok(), await token.text()).toBeTruthy();
  expect(token.headers()["cache-control"]).toContain("no-store");
  expect(token.headers()["pragma"]).toBe("no-cache");
  const accessToken = String((await token.json()).access_token);
  const polled = await request.get(`${apiPath}/mock/demo-pull/events`, {
    params: { simulation_id: oauthId, limit: 1 },
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  expect(polled.ok(), await polled.text()).toBeTruthy();

  await page.goto(`/simulations/${oauthId}`);
  await expect(page.getByText("Issued tokens (metadata only)")).toBeVisible();
  await expect(page.getByText(`browser-client-${runId}`)).toBeVisible();
  await expect(page.getByText(/token prefix/i)).toHaveCount(0);
});

test("Sophos token, discovery, and cursor workflow uses complete live URLs", async ({
  page,
  request,
}) => {
  await page.goto(`/simulations/${sophosId}`);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText("Dataset items").locator(".."))
    .toContainText("205");
  await expect(page.getByText(`POST ${process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080"}/api/v1/mock/sophos-central`, { exact: false }).first())
    .toBeVisible();

  const tokenResponse = await request.post(
    `${apiPath}/mock/sophos-central/api/v2/oauth2/token`,
    {
      params: { simulation_id: sophosId },
      form: {
        grant_type: "client_credentials",
        client_id: `sophos-browser-client-${runId}`,
        client_secret: sophosClientSecret,
        scope: "token",
      },
    },
  );
  expect(tokenResponse.ok(), await tokenResponse.text()).toBeTruthy();
  const accessToken = String((await tokenResponse.json()).access_token);
  const authorization = { Authorization: `Bearer ${accessToken}` };
  const whoami = await request.get(`${apiPath}/mock/sophos-central/whoami/v1`, {
    params: { simulation_id: sophosId },
    headers: authorization,
  });
  expect((await whoami.json()).id).toBe(sophosTenantId);

  const first = await request.get(`${apiPath}/mock/sophos-central/siem/v1/events`, {
    params: { simulation_id: sophosId, limit: 200 },
    headers: { ...authorization, "X-Tenant-ID": sophosTenantId },
  });
  expect(first.ok(), await first.text()).toBeTruthy();
  const firstPage = (await first.json()) as { items: unknown[]; next_cursor: string };
  expect(firstPage.items).toHaveLength(200);
  const continuation = await request.get(`${apiPath}/mock/sophos-central/siem/v1/events`, {
    params: { simulation_id: sophosId, limit: 200, cursor: firstPage.next_cursor },
    headers: { ...authorization, "X-Tenant-ID": sophosTenantId },
  });
  expect(((await continuation.json()) as { items: unknown[] }).items).toHaveLength(5);
});

test("Okta System Log and event-hook action work against the real receiver", async ({
  page,
  request,
}) => {
  expect((await request.post(`${apiPath}/simulations/${oktaPullId}/start`)).ok()).toBeTruthy();
  const logs = await request.get(`${apiPath}/mock/okta/api/v1/logs`, {
    params: { simulation_id: oktaPullId, limit: 2, sortOrder: "ASCENDING" },
    headers: { Authorization: `SSWS ${oktaApiToken}` },
  });
  expect(logs.ok(), await logs.text()).toBeTruthy();
  expect(Array.isArray(await logs.json())).toBeTruthy();
  expect(logs.headers().link).toContain('rel="self"');
  expect(logs.headers().link).toContain('rel="next"');

  await page.goto(`/simulations/${oktaHookId}`);
  await page.getByRole("button", { name: "Verify event-hook endpoint" }).click();
  await expect(page.getByText("verify-event-hook: verified (HTTP 200)")).toBeVisible();
  await page.getByRole("button", { name: "Send one now" }).click();
  await expect(page.getByText("Successful").locator("..")).toContainText("2");
});
