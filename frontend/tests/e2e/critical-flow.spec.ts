import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, user = "admin", pass = "Admin@2026") {
  await page.goto("/login");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(pass);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Command center" })).toBeVisible();
}

async function kpi(page: Page, label: string): Promise<number> {
  const card = page.locator("main").getByRole("link", { name: new RegExp(`^${label}\\s+\\d`, "i") });
  await expect(card).toBeVisible();
  const text = await card.innerText();
  return Number(text.split("\n").map((s) => s.trim()).find((s) => /^\d+$/.test(s)));
}

test("critical flow: create → analyse → review → decision → audit → dashboard", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  await login(page);
  await page.getByLabel("Time window").selectOption("30");
  await expect(page.getByText("HSE intelligence / Last 30 days", { exact: false })).toBeVisible();
  const totalBefore = await kpi(page, "Total reports");
  const queueBefore = await kpi(page, "Review queue");

  // 1. create report (demo case), analyse
  await page.goto("/reports/new");
  await page.getByRole("button", { name: "Vehicle + pedestrian" }).click();
  await page.getByRole("button", { name: /Analyze report/i }).click();

  // 2. live pipeline + result
  const result = page.locator("#result");
  await expect(result).toBeVisible({ timeout: 20_000 });
  await expect(result.getByText(/Routed to human review — Insufficient information/)).toBeVisible();
  const reportId = (await result.locator("p.font-mono").first().innerText()).trim();
  expect(reportId).toMatch(/^RPT-\d{4}-\d{4}$/);

  // 3. investigation view: extraction, energy, control, SCL, SIF, IOGP, priority
  await result.getByRole("button", { name: /Open full investigation/ }).click();
  await expect(page.getByRole("heading", { name: reportId })).toBeVisible();
  const orig = page.locator("#orig");
  await expect(orig.locator("mark", { hasText: "Vehicle" }).first()).toBeVisible();
  const scl = page.locator("#scl");
  await expect(scl.getByText("High energy?").first()).toBeVisible();
  await expect(scl.getByText("Direct control?").first()).toBeVisible();
  await expect(scl.getByText("No direct control or barrier is stated in the report.")).toBeVisible();
  await expect(scl.getByText("Undetermined").first()).toBeVisible();
  const iogp = page.locator("#iogp");
  await expect(iogp.getByText("Driving", { exact: true })).toBeVisible();
  await expect(iogp.getByText(/Requires independent HSE expert validation/)).toBeVisible();
  await expect(page.locator("#priority").getByText("/ 100")).toBeVisible();

  // 4. dashboard reflects the new report and the review item
  await page.goto("/");
  await page.getByLabel("Time window").selectOption("30");
  await expect.poll(() => kpi(page, "Total reports")).toBe(totalBefore + 1);
  await expect.poll(() => kpi(page, "Review queue")).toBe(queueBefore + 1);

  // 5. reviewer decision from the report page
  await page.goto(`/reports/${reportId}`);
  const review = page.locator("#review");
  await review.getByText("Change", { exact: true }).click();
  await review.getByLabel("SCL class").selectOption("EXPOSURE");
  await review.getByLabel(/Reason \(required\)/).fill("No pedestrian segregation at the gantry; no direct control existed.");
  await review.getByLabel("Note", { exact: true }).fill("Traffic management action raised (demo).");
  await review.getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText("Human confirmed").first()).toBeVisible();
  await expect(page.getByText("Final decision: HSE reviewer")).toBeVisible();

  // 6. audit record
  const audit = page.locator("#audit");
  await expect(audit.getByText(/REVIEW_COMPLETED/)).toBeVisible();
  await expect(audit.getByText(/CHANGE · HSE Admin \(demo\)/)).toBeVisible();

  // 7. dashboard updates after review
  await page.goto("/");
  await page.getByLabel("Time window").selectOption("30");
  await expect.poll(() => kpi(page, "Review queue")).toBe(queueBefore);

  expect(errors.filter((e) => !/favicon|Download the React DevTools/i.test(e))).toEqual([]);
});

test("all routes render without errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  for (const [path, heading] of [
    ["/reports", "Safety reports"],
    ["/patterns", "Pattern explorer"],
    ["/import", "Import data"],
    ["/taxonomy", "Taxonomy"],
    ["/review", "Review queue"],
    ["/model", "Model / analysis"],
    ["/settings", "Settings"],
    ["/audit", "Audit log"],
    ["/reports/new", "New report"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
  await page.goto("/patterns");
  await page.locator('a[href^="/patterns/"]').first().click();
  await expect(page.getByText("Connected reports")).toBeVisible();
  expect(errors).toEqual([]);
});

test("report search and filters", async ({ page }) => {
  await login(page);
  await page.goto("/reports");
  await page.getByLabel("Search reports").fill("SYN-DEMO-003");
  await expect(page.getByRole("link", { name: "SYN-DEMO-003" }).first()).toBeVisible();
  await expect(page.getByText(/^1 report$/)).toBeVisible();
  await page.goto("/reports?sif_signal=SIF_POTENTIAL");
  await expect(page.getByText(/reports?$/).first()).toBeVisible();
  const badges = page.locator("tbody").getByText("SIF POTENTIAL");
  await expect(badges.first()).toBeVisible();
});

test("officer cannot reach admin-only pages", async ({ page }) => {
  await login(page, "officer", "Officer@2026");
  await expect(page.getByRole("link", { name: "Taxonomy" })).toHaveCount(0);
  await page.goto("/taxonomy");
  await expect(page.getByText("Restricted to HSE Admin")).toBeVisible();
});

test("csv import updates the registry", async ({ page }) => {
  await login(page);
  await page.goto("/import");
  const id = `E2E-${Date.now().toString().slice(-6)}`;
  const today = new Date().toISOString().slice(0, 10);
  const csv = `report_id,report_type,date,site,location,activity,equipment,description\n${id},Unsafe Act,${today},Moran,OCS-1 Moran,Hot work,Grinder,"Grinding near the tank manifold without a gas test and without a fire blanket."\nBAD-1,Unknown,${today},Moran,X,Y,Z,"too short"\n`;
  await page.locator("#csv").setInputFiles({ name: "e2e.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  const validation = page.locator("#validation");
  await expect(validation.getByText("Rows detected")).toBeVisible();
  await expect(validation.getByText("report_type must be")).toBeVisible();
  await page.getByRole("button", { name: /Import & analyse 1 rows/ }).click();
  await expect(page.getByText("Import complete")).toBeVisible({ timeout: 30_000 });
  await page.goto(`/reports/${id}`);
  await expect(page.getByRole("heading", { name: id })).toBeVisible();
  await expect(page.locator("#iogp").getByText("Hot Work", { exact: true })).toBeVisible();
});
