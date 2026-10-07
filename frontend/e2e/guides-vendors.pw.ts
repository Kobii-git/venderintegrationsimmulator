import { expect, test } from "@playwright/test";
import { gunzipSync } from "node:zlib";
import { Buffer } from "node:buffer";

test("offline guides filter, navigate, download, contents and vendor raw logs", async ({ page }) => {
 const errors: string[]=[]; page.on("pageerror", error=>errors.push(error.message));
 await page.addInitScript(() => {
  Object.defineProperty(navigator, "clipboard", { value: { writeText: async (value: string) => { document.documentElement.dataset.copied = value; } } });
  window.print = () => { document.documentElement.dataset.printed = "yes"; };
 });
 await page.goto("/");
 await page.getByRole("link", { name:"Deployment Guides" }).click();
 await expect(page.getByRole("heading", { name:"Deployment Guides" })).toBeVisible();
 await page.getByLabel("Vendor", { exact:true }).selectOption("cloudflare");
 await page.getByLabel("Connection method").selectOption("Native connector");
 await page.getByRole("link", { name:"Cloudflare: Azure Blob and Sentinel CCF" }).click();
 await expect(page.getByRole("heading", { name:"Cloudflare: Azure Blob Storage and Sentinel CCF", exact:true })).toBeVisible();
 await page.getByText("Documentation: complete — deployment verification", {exact:true}).click();
 await expect(page.getByRole("table").first()).toContainText("not_run");
 await page.getByRole("button", {name:"Copy command", exact:true}).first().click();
 await expect(page.getByRole("button", {name:"Copied", exact:true}).first()).toBeVisible();
 expect(await page.locator("html").getAttribute("data-copied")).toBeTruthy();
 await page.getByRole("button", {name:"Print guide", exact:true}).click();
 await expect(page.locator("html")).toHaveAttribute("data-printed", "yes");
 await page.getByRole("link", { name:"Troubleshooting", exact:true }).click();
 await expect(page).toHaveURL(/#troubleshooting$/);
 const downloadPromise=page.waitForEvent("download");
 await page.getByRole("button",{name:"Download Markdown"}).click();
 expect((await downloadPromise).suggestedFilename()).toBe("cloudflare-azure-blob.md");
 await page.getByRole("link",{name:"Generate raw log",exact:true}).last().click();
 await expect(page.getByLabel("Product",{exact:true})).toHaveValue("cloudflare");
 await expect(page.getByLabel("action", {exact:true})).toHaveCount(0);
 await page.getByRole("button",{name:"Generate raw log",exact:true}).click();
 await expect(page.getByLabel("Raw log output")).toHaveValue(/RayID/);
 for (const [vendor,method] of [["fortinet","native"],["upguard","native"],["mimecast","native"],["upguard","azure-ingestion"]]) {
  await page.goto(`/guides/${vendor}/${method}`);
  await expect(page.getByRole("heading",{name:"Production deployment",exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Simulator testing",exact:true})).toBeAttached();
  await expect(page.getByRole("button",{name:"Copy command"}).first()).toBeAttached();
 }
 expect(errors).toEqual([]);
});

test("Cloudflare saved Log Lab native wire and Mimecast saved OAuth batch downloads", async ({page,request})=>{
 await page.goto('/lab');
 await page.getByLabel('Name',{exact:true}).fill('Cloudflare browser native');
 await page.getByLabel('Source',{exact:true}).selectOption('cloudflare');
 await page.getByLabel('HTTP Request',{exact:true}).check();
 await page.getByLabel('Collector 1 transport').selectOption('cloudflare_logpush');
 await page.locator('input[type="url"]').fill('http://receiver:9000/cloudflare');
 await page.getByRole('button',{name:'Create lab',exact:true}).click();
 await expect(page).toHaveURL(/\/simulations\/[a-f0-9-]+$/);
 const cloudId=page.url().split('/').at(-1)!;
 const cloud=await (await request.get(`/api/v1/simulations/${cloudId}`)).json();
 const preview=await request.post(`/api/v1/simulations/${cloudId}/wire-preview?target_id=${cloud.targets[0].id}`);
 expect(preview.status()).toBe(200);
 const wire=await preview.json();
 expect(wire.compression).toBe('gzip');
 expect(JSON.parse(gunzipSync(Buffer.from(wire.wire_base64,'base64')).toString()).ClientIP).toBeDefined();
 const sent=await request.post(`/api/v1/simulations/${cloudId}/send`);
 expect((await sent.json()).delivery_success).toBe(true);
 await request.delete(`/api/v1/simulations/${cloudId}`);
 const created=await request.post('/api/v1/simulations',{data:{name:'Mimecast browser native',product_id:'mimecast',scenario_id:'email-receipt',scenario_ids:['email-receipt','email-delivery'],simulation_mode:'pull_api',schedule:{type:'manual'},auth_config:{auth_method_id:'none',oauth_client_id:'browser-client',oauth_client_secret:'browser-secret'},inbound_config:{auth_method_id:'oauth2_client_credentials',dataset_size:3}}});
 expect(created.status()).toBe(201);
 const sim=await created.json();
 await request.post(`/api/v1/simulations/${sim.id}/start`);
 const token=await request.post(`/api/v1/mock/mimecast/oauth/token?simulation_id=${sim.id}`,{form:{grant_type:'client_credentials',client_id:'browser-client',client_secret:'browser-secret'}});
 expect(token.status()).toBe(200);
 const batch=await request.get(`/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id=${sim.id}&pageSize=2`,{headers:{Authorization:`Bearer ${(await token.json()).access_token}`}});
 const body=await batch.json(); expect(body['@nextPage']).toBeTruthy();
 const file=await request.get(body.value[0].url); expect(file.status()).toBe(200);
 expect(gunzipSync(await file.body()).toString().trim().split('\n')).toHaveLength(2);
 await page.goto(`/simulations/${sim.id}/edit`);
 await expect(page.getByText(/API 2.0/)).toBeVisible();
 await request.delete(`/api/v1/simulations/${sim.id}`);
});
