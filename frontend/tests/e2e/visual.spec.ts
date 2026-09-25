import { expect, test } from "@playwright/test";

// Responsive check: no route may scroll horizontally at any supported width.
const WIDTHS = [1440, 1280, 1024, 768, 390];
const ROUTES = ["/", "/reports", "/reports/SYN-DEMO-001", "/reports/new", "/review", "/patterns", "/import", "/model", "/settings", "/taxonomy", "/audit"];

test("no horizontal page overflow at supported widths", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("Admin@2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Command center" })).toBeVisible();
  const problems: string[] = [];
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 900 });
    for (const r of ROUTES) {
      await page.goto(r);
      await page.locator("h1").first().waitFor();
      await page.waitForTimeout(400);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 1) problems.push(`${r} @${w}px overflows by ${over}px`);
      if (process.env.SHOTS && (w === 1440 || w === 390) && ["/", "/reports/SYN-DEMO-001", "/patterns", "/model"].includes(r)) {
        await page.screenshot({ path: `test-results/shots/${w}${r.replace(/\//g, "_") || "_root"}.png`, fullPage: w === 390 ? false : true });
      }
    }
  }
  expect(problems).toEqual([]);
});
