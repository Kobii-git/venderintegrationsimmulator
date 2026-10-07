import { Buffer } from "node:buffer";
import { expect, test } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080";
test.use({ baseURL });

test("build and edit a multi-collector lab with devices and uploaded replay", async ({ page, request }) => {
  const name = `Browser log lab ${Date.now()}`;
  const datasetName = `${name}.ndjson`;
  await page.goto("/lab");
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Find a source").fill("domain");
  await page.getByLabel("Source", { exact: true }).selectOption("windows-dc");
  await page.getByLabel("Logon Failure", { exact: true }).check();
  await page.getByLabel("User pool (one name per line)").fill("alice\nbob");
  await page.getByLabel("Correlated incident preset").selectOption("password_spray");
  await page.getByRole("button", { name: "Add device" }).click();
  await page.getByLabel("Device 1 hostname").fill("dc01.browser.test");
  await page.getByLabel("Device 1 IP").fill("192.0.2.55");
  await page.getByLabel("Collector 1 host").fill("127.0.0.1");
  await page.getByRole("button", { name: "Add collector" }).click();
  await page.getByLabel("Collector 2 transport").selectOption("http_webhook");
  await page.locator('input[type="url"]').fill("http://127.0.0.1:9000/lab");
  await page.getByLabel("Collector 2 payload format").selectOption("json");
  await page.getByLabel("Upload log dataset").setInputFiles({ name: datasetName, mimeType: "application/x-ndjson", buffer: Buffer.from('{"TimeGenerated":"2020-01-01T00:00:00Z","customDate":"2020-01-01T00:00:00Z","msg":"browser lab"}\n') });
  await expect(page.getByRole("option", { name: `${datasetName} (1 records)` })).toBeAttached();
  await page.getByLabel("Loop dataset").check();
  await page.getByLabel("Rewrite recognized timestamps to current time").check();
  await page.getByRole("button", { name: "Preview dataset" }).click();
  await expect(page.locator("pre")).toContainText('"unknown_timestamp_fields"');
  await expect(page.locator("pre")).toContainText('"customDate"');
  await expect(page.locator("input:invalid")).toHaveCount(0);
  await page.getByRole("button", { name: "Create lab", exact: true }).click();
  await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
  const id = page.url().split("/").at(-1)!;
  const simulation = await (await request.get(`/api/v1/simulations/${id}`)).json();
  expect(simulation.targets).toHaveLength(2);
  expect(simulation.schedule.user_pool).toEqual(["alice", "bob"]);
  expect(simulation.schedule.incident_preset).toBe("password_spray");
  expect(simulation.devices[0].hostname).toBe("dc01.browser.test");
  expect(simulation.replay_config.loop).toBe(true);
  await expect(page.getByRole("heading", { name: "Collector delivery" })).toBeVisible();
  await page.getByRole("link", { name: "Collectors & replay" }).click();
  await expect(page.getByLabel("Collector 2 transport")).toHaveValue("http_webhook");
  await page.getByRole("button", { name: "Preview saved wire bytes" }).first().click();
  await expect(page.locator("pre")).toContainText('"wire_base64"');
  await page.getByLabel("Collector 1 name").fill("Renamed primary");
  await page.getByRole("button", { name: "Save lab" }).click();
  await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
  const exported = await (await request.get(`/api/v1/simulations/${id}/export`)).json();
  expect(exported.format_version).toBe("3.0");
  expect(exported.simulation.targets[0].name).toBe("Renamed primary");
  expect(exported.simulation.targets).toHaveLength(2);
  await request.delete(`/api/v1/simulations/${id}`);
  await request.delete(`/api/v1/datasets/${simulation.replay_config.dataset_id}`);
});

test("Log Lab opens and saves on HTTP origins without randomUUID", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/lab");
  await expect(page.getByRole("heading", { name: "Build a log lab" })).toBeVisible();
  await page.getByLabel("Source", { exact: true }).selectOption("uploaded-logs");
  await page.getByRole("checkbox", { name: "Uploaded record", exact: true }).check();
  await page.getByLabel("Name", { exact: true }).fill("HTTP LAN regression");
  await page.getByRole("button", { name: "Add device" }).click();
  await expect(page.getByLabel("Device 1 hostname")).toBeVisible();
  await page.getByRole("button", { name: "Add collector" }).click();
  await expect(page.getByLabel("Collector 2 name")).toBeVisible();
  await page.getByRole("button", { name: "Remove collector" }).last().click();
  await page.getByLabel("Collector 1 transport").selectOption("http_webhook");
  await page.getByLabel("Collector 1 payload format").selectOption("json");
  await page.locator('input[type="url"]').fill("https://example.test/webhook");
  await page.getByRole("button", { name: "Create lab" }).click();
  await expect(page).toHaveURL(/\/simulations\/[^/]+$/);
  expect(errors).toEqual([]);
  const id = page.url().split("/").pop();
  await page.request.delete(`/api/v1/simulations/${id}`);
});

test("Upload logs creates a target without randomUUID", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
  });
  await page.route("**/api/v1/simulations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const body = route.request().postDataJSON();
    expect(body.targets[0].id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    await route.fulfill({ status: 422, json: { error: { code: "validation_error", message: "Target creation verified" } } });
  });
  let releaseList!: () => void;
  const delayedList = new Promise<void>((resolve) => { releaseList = resolve; });
  await page.route("**/api/v1/datasets", async (route) => {
    await delayedList;
    await route.fulfill({ status: 200, json: [] });
  });
  await page.goto("/uploads");
  await page.getByRole("combobox", { name: "File format", exact: true }).selectOption("json");
  await page.getByLabel("Log file", { exact: true }).setInputFiles({
    name: "http-lan.json",
    mimeType: "application/json",
    buffer: Buffer.from('[{"Time":"2026-10-06T20:00:00Z","Application":"IntegrationSimulator","RawData":"HTTP LAN test"}]'),
  });
  await expect(page.getByLabel("Dataset")).not.toHaveValue("");
  releaseList();
  await expect(page.getByLabel("Dataset")).not.toHaveValue("");
  await page.getByRole("combobox", { name: "Payload mode", exact: true }).selectOption("json");
  await page.getByLabel("DCE endpoint").fill("https://example.ingest.monitor.azure.com");
  await page.getByLabel("Tenant ID", { exact: true }).fill("tenant");
  await page.getByLabel("DCR immutable ID").fill("dcr-test");
  await page.getByLabel("Stream name").fill("Custom-Test");
  await page.getByLabel("Client ID", { exact: true }).fill("client");
  await page.getByLabel("Client secret", { exact: true }).fill("local-test-secret");
  await page.getByRole("button", { name: "Upload to Azure" }).click();
  await expect(page.getByText("Target creation verified")).toBeVisible();
  const datasetId = await page.getByLabel("Dataset").inputValue();
  await page.request.delete(`/api/v1/datasets/${datasetId}`);
});
