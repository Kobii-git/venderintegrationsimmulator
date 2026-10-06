import { Buffer } from "node:buffer";
import type { SimulationResponse } from "../src/types/api";
import { expect, test } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080";
test.use({ baseURL });

test("validate Azure uploads, configure relay, and track accepted records", async ({
  page,
  request,
}) => {
  await page.goto("/uploads");
  await page.getByLabel("Log file", { exact: true }).setInputFiles({
    name: "azure-browser.ndjson",
    mimeType: "application/x-ndjson",
    buffer: Buffer.from(
      '{"TimeGenerated":"2020-01-01T00:00:00Z","Message":"browser upload","count":3}\n',
    ),
  });
  await expect(page.getByLabel("Dataset", { exact: true })).not.toHaveValue("");
  await page.getByRole("button", { name: "Validate and preview" }).click();
  await expect(page.getByLabel("Ingestion preview")).toContainText('"RawData"');
  await page.getByLabel("Payload mode").selectOption("json");
  await page.getByRole("button", { name: "Validate and preview" }).click();
  await expect(page.getByLabel("Ingestion preview")).toContainText(
    '"count": 3',
  );
  await expect(page.getByLabel("Ingestion preview")).not.toContainText(
    '"RawData"',
  );
  await page.getByLabel("DCE endpoint").fill("https://dce.example.test");
  await page.getByLabel("Tenant ID").fill("tenant");
  await page.getByLabel("DCR immutable ID").fill("dcr-browser");
  await page.getByLabel("Stream name").fill("Custom-Browser");
  await page.getByLabel("Client ID").fill("client");
  await page.getByLabel("Client secret").fill("browser-client-canary");
  await page.getByLabel("Delivery path").selectOption("azure_function_app");
  await page
    .getByLabel("Function ingestion URL")
    .fill("https://relay.example.test/api/ingest");
  await page.getByLabel("Function key").fill("browser-function-canary");
  const diagnostics: string[] = [];
  await page.route("**/api/v1/transport/azure/*", async (route) => {
    diagnostics.push(route.request().url().split("/").at(-1)!);
    await route.fulfill({
      json: {
        success: true,
        delivery_note: "Authentication/configuration only; no records sent",
      },
    });
  });
  await page.getByRole("button", { name: "Check authentication" }).click();
  await expect(page.getByLabel("Connection result")).toContainText(
    "no records sent",
  );
  expect(diagnostics).toEqual(["test"]);
  await page
    .getByRole("button", { name: "Send test record", exact: true })
    .click();
  await expect.poll(() => diagnostics.length).toBe(2);
  expect(diagnostics).toEqual(["test", "send"]);
  // Mock remote acceptance, while upload, validation, configuration and secret persistence use real API.
  let saved: SimulationResponse | null = null;
  await page.route("**/api/v1/simulations/*/start", async (route) => {
    const id = route.request().url().split("/").at(-2)!;
    saved = await (await request.get(`/api/v1/simulations/${id}`)).json();
    await route.fulfill({ json: { ...saved, status: "running" } });
  });
  await page.route(/\/api\/v1\/simulations\/[^/]+$/, async (route) => {
    if (route.request().method() !== "GET" || !saved) {
      await route.continue();
      return;
    }
    await route.fulfill({
      json: {
        ...saved,
        status: "completed",
        targets: saved.targets?.map((t) => ({
          ...t,
          stats: { successful: 1, failed: 0, queued: 0 },
        })),
        runtime_stats: {
          ...saved.runtime_stats,
          events_generated: 1,
          events_successful: 1,
          events_failed: 0,
        },
      },
    });
  });
  await page
    .getByRole("button", { name: "Upload to Azure", exact: true })
    .click();
  await expect(page.getByLabel("Upload progress")).toContainText(
    "Status: completed",
  );
  await expect(page.getByLabel("Upload progress")).toContainText(
    "Azure-accepted: 1",
  );
  const stored = saved! as SimulationResponse;
  expect(stored.product_id).toBe("uploaded-logs");
  expect(stored.targets![0].auth_config.has_token).toBe(true);
  expect(JSON.stringify(stored)).not.toContain("browser-function-canary");
  await page.unrouteAll({ behavior: "wait" });
  await page.goto(`/lab/${stored.id}`);
  await expect(page.getByLabel("Collector 1 transport")).toHaveValue(
    "azure_function_app",
  );
  await expect(page.getByLabel("Function ingestion URL")).toHaveValue(
    "https://relay.example.test/api/ingest",
  );
  await request.delete(`/api/v1/simulations/${stored.id}`);
  await request.delete(
    `/api/v1/datasets/${(stored.replay_config as { dataset_id: string }).dataset_id}`,
  );
});
