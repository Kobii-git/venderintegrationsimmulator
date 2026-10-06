import { Buffer } from "node:buffer";
import { expect, test } from "@playwright/test";

test("generate four UpGuard raw JSON examples, download, and inspect native logs", async ({
  page,
  request,
}) => {
  const before = await (await request.get("/api/v1/simulations")).json();
  await page.goto("/");
  await page.getByRole("link", { name: "Generate raw log" }).click();
  await expect(page.getByLabel("Product", { exact: true })).toHaveValue(
    "upguard",
  );
  const output = page.getByLabel("Raw log output");
  for (const [scenario, type] of [
    ["score-threshold", "CustomerCSTARUnderThreshold"],
    ["data-leak", "DataLeakPublished"],
    ["identity-breach", "IdentityBreachPublished"],
    ["vulnerability", "NewVulnerabilityDetected"],
  ]) {
    await page.getByLabel("Scenario", { exact: true }).selectOption(scenario);
    await page
      .getByRole("button", { name: "Generate raw log", exact: true })
      .click();
    await expect(output).toHaveValue(new RegExp(type));
    const body = JSON.parse(await output.inputValue());
    expect(body.notification.type).toBe(type);
    expect(typeof body.notification.id).toBe("number");
    expect(body._simulator).toBeUndefined();
  }
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download raw log" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("upguard-vulnerability.json");
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream!) chunks.push(chunk);
  expect(Buffer.concat(chunks).toString()).toBe(await output.inputValue());
  await page.getByLabel("Payload mode").selectOption("troubleshooting");
  await expect(output).toHaveCount(0);
  await page
    .getByRole("button", { name: "Generate raw log", exact: true })
    .click();
  await expect(output).toHaveValue(/_simulator/);
  await page.getByLabel("Product", { exact: true }).selectOption("fortinet");
  await expect(page.getByLabel("Scenario", { exact: true })).toHaveValue(
    "forward-traffic-allow",
  );
  await page
    .getByRole("button", { name: "Generate raw log", exact: true })
    .click();
  await expect(output).toHaveValue(/srcip=/);
  expect(await output.inputValue()).not.toContain("_syslog_message");
  expect(await (await request.get("/api/v1/simulations")).json()).toEqual(
    before,
  );
});
