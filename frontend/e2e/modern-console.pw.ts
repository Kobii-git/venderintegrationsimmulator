import { expect, test } from "@playwright/test";

const next = async (page: import("@playwright/test").Page) => {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
};

test("guided creation validates, retains edits, reviews, and saves without sending", async ({ page, request }) => {
  const writes: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/simulations")) writes.push(req.url());
  });
  await page.goto("/simulations/new");
  await next(page);
  await expect(page.getByRole("alert")).toContainText("Enter a simulation name");
  await expect(page.getByRole("button", { name: /4 Review/ })).toBeDisabled();
  await page.getByLabel("Simulation name", { exact: true }).fill("Console guided push");
  await page.getByLabel("Product", { exact: true }).selectOption("upguard");
  await expect(page.getByRole("checkbox", { name: "Data Leak Detected (data-leak)" })).toBeVisible();
  await next(page);
  await expect(page.getByRole("alert")).toContainText("Select at least one scenario");
  await page.getByRole("checkbox", { name: "Data Leak Detected (data-leak)" }).check();
  await next(page);
  await expect(page.getByRole("heading", { name: "Connection", exact: true })).toBeFocused();
  await next(page);
  await expect(page.getByRole("alert")).toContainText("highlighted field");
  await page.getByLabel("Webhook URL", { exact: true }).fill("https://collector.example/hook?sig=wizard-secret");
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.getByLabel("Simulation name", { exact: true })).toHaveValue("Console guided push");
  await next(page);
  await expect(page.getByLabel("Webhook URL", { exact: true })).toHaveValue(/wizard-secret/);
  await next(page);
  await page.getByLabel("Mode", { exact: true }).selectOption("finite");
  await page.getByLabel("Interval (seconds)", { exact: true }).fill("0");
  await next(page);
  await expect(page.getByRole("heading", { name: "Schedule & behavior", exact: true })).toBeVisible();
  await page.getByLabel("Interval (seconds)", { exact: true }).fill("15");
  await page.getByLabel("Event count", { exact: true }).fill("3");
  await next(page);
  await expect(page.getByRole("heading", { name: "Review & save" })).toBeVisible();
  await expect(page.getByText("https://collector.example/hook", { exact: true })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("wizard-secret");
  expect(writes).toEqual([]);
  await page.getByRole("button", { name: "Create simulation", exact: true }).click();
  await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
  const id = page.url().split("/").at(-1)!;
  try {
    const saved = await (await request.get(`/api/v1/simulations/${id}`)).json();
    expect(saved.schedule).toMatchObject({ type: "finite", interval_seconds: 15, event_count: 3 });
    expect(saved.runtime_stats.events_attempted).toBe(0);
    expect(saved.status).toBe("stopped");
    expect(writes).toHaveLength(1);
  } finally { await request.delete(`/api/v1/simulations/${id}`); }
});

for (const profile of ["demo-syslog", "demo-pull"]) {
  test(`guided ${profile} setup keeps its transport and mode`, async ({ page, request }) => {
    await page.goto("/simulations/new");
    await page.getByLabel("Simulation name", { exact: true }).fill(`Console ${profile}`);
    await page.getByLabel("Product", { exact: true }).selectOption(profile);
    await page.getByRole("checkbox").first().check();
    await next(page);
    if (profile === "demo-syslog") {
      await expect(page.getByLabel("Syslog host", { exact: true })).toBeVisible();
      await page.getByLabel("Syslog host", { exact: true }).fill("192.0.2.10");
    } else {
      await expect(page.getByText("Inbound mock API", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Webhook URL")).toHaveCount(0);
    }
    await next(page);
    if (profile === "demo-pull") await page.getByLabel("Items per route").fill("7");
    await next(page);
    await page.getByRole("button", { name: "Create simulation", exact: true }).click();
    await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
    const id = page.url().split("/").at(-1)!;
    try {
      const saved = await (await request.get(`/api/v1/simulations/${id}`)).json();
      expect(saved.simulation_mode).toBe(profile === "demo-pull" ? "pull_api" : "push_webhook");
      if (profile === "demo-syslog") expect(saved.destination).toMatchObject({ transport_id: "syslog", host: "192.0.2.10" });
      else expect(saved.inbound_config.dataset_size).toBe(7);
      expect(saved.status).toBe("stopped");
    } finally { await request.delete(`/api/v1/simulations/${id}`); }
  });
}

test("dashboard search, status, secondary actions and keyboard cancellation", async ({ page, request }) => {
  const created = await request.post("/api/v1/simulations", { data: {
    name: "Console dashboard example", product_id: "upguard", scenario_ids: ["data-leak"],
    simulation_mode: "push_webhook", schedule: { type: "manual" },
    destination: { transport_id: "http_webhook", url: "https://collector.example/hook" },
  } });
  expect(created.status()).toBe(201);
  const id = (await created.json()).id;
  try {
    await page.goto("/");
    await page.getByLabel("Search simulations").fill("Console dashboard example");
    const row = page.getByRole("list", { name: "Simulations", exact: true }).getByRole("listitem");
    await expect(row).toHaveCount(1);
    await expect(row.getByRole("button", { name: "Send", exact: true })).toBeEnabled();
    await page.getByLabel("Filter by status").selectOption("running");
    await expect(page.getByText("No matching simulations")).toBeVisible();
    await page.getByLabel("Filter by status").selectOption("stopped");
    const more = row.locator("summary");
    await more.click();
    await row.getByRole("button", { name: "Delete", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Delete simulation?" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(dialog.getByRole("button", { name: "Delete" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(more).toBeFocused();
    expect((await request.get(`/api/v1/simulations/${id}`)).status()).toBe(200);
  } finally { await request.delete(`/api/v1/simulations/${id}`); }
});

test("responsive console navigation and key screens fit narrow viewports", async ({ page }) => {
  for (const width of [320, 390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/simulations/new", "/guides", "/uploads", "/raw-logs", "/lab"]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    if (width < 760) {
      const menu = page.getByRole("button", { name: "Menu", exact: true });
      await expect(page.getByRole("navigation", { name: "Main navigation" })).not.toBeVisible();
      await menu.click();
      await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
      await page.getByRole("link", { name: "Generate raw log", exact: true }).focus();
      await page.keyboard.press("Escape");
      await expect(menu).toHaveAttribute("aria-expanded", "false");
      await expect(menu).toBeFocused();
      await menu.click();
      await page.getByRole("link", { name: "Deployment Guides", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Deployment Guides", exact: true })).toBeVisible();
      await expect(menu).toHaveAttribute("aria-expanded", "false");
    }
  }
});
