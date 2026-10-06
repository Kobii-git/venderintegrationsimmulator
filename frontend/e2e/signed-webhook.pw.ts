import { expect, test } from "@playwright/test";

test("paste a signed webhook URL, test, save, edit and send without exposing its signature", async ({
  page,
  request,
}) => {
  const signature = "browser-logic-signature+slash/=";
  const base = `http://${process.env.E2E_RECEIVER_HOST ?? "receiver"}:9000/logic-callback`;
  const query = new URLSearchParams({
    "api-version": "2016-10-01",
    sp: "/triggers/manual/run",
    sv: "1.0",
    sig: signature,
  });
  await page.goto("/simulations/new");
  await page
    .getByLabel("Simulation name", { exact: true })
    .fill("Signed URL browser regression");
  await page.getByLabel("Product", { exact: true }).selectOption("upguard");
  await page
    .getByRole("checkbox", { name: "Data Leak Detected (data-leak)" })
    .check();
  await page
    .getByLabel("Webhook URL", { exact: true })
    .fill(base + "?" + query);
  await page.getByLabel("Mode", { exact: true }).selectOption("manual");
  await page
    .getByRole("button", { name: "Test connection", exact: true })
    .click();
  await expect(page.getByText(/Connection OK/)).toBeVisible();
  await page
    .getByRole("button", { name: "Create simulation", exact: true })
    .click();
  await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
  const id = page.url().split("/").at(-1)!;
  try {
    const saved = await request.get(`/api/v1/simulations/${id}`);
    const data = await saved.json();
    expect(data.destination.url).toBe(base);
    expect(data.destination.query_params).toEqual(
      [...query.keys()].map((name) => ({
        name,
        sensitive: true,
        has_value: true,
      })),
    );
    expect(await saved.text()).not.toContain(signature);
    await page.goto(`/simulations/${id}/edit`);
    await expect(page.getByLabel("Webhook URL", { exact: true })).toHaveValue(
      base,
    );
    await expect(page.getByLabel("URL query parameters value 4")).toHaveValue(
      "",
    );
    await expect(
      page.getByLabel("URL query parameters value 4"),
    ).toHaveAttribute("type", "password");
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(page).toHaveURL(`/simulations/${id}`);
    await page
      .getByRole("button", { name: "Send one now", exact: true })
      .click();
    await expect(
      page.getByText("Successful", { exact: true }).locator(".."),
    ).toContainText("1");
    const exported = await request.get(`/api/v1/simulations/${id}/export`);
    expect(await exported.text()).not.toContain(signature);
    expect(await page.locator("body").innerText()).not.toContain(signature);
  } finally {
    await request.delete(`/api/v1/simulations/${id}`);
  }
});
