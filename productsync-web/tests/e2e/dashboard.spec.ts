import { test, expect, Page } from "@playwright/test";

async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/en/login");
  await page.fill("input[type='email']", email);
  await page.fill("input[type='password']", password);
  await page.click("button[type='submit']");
  await page.waitForURL(/dashboard/, { timeout: 8000 });
}

test.describe("Dashboard (authenticated)", () => {
  // Uses a pre-existing test account — adjust credentials as needed
  const EMAIL = "test@productsync.com";
  const PASS = "testpass123";

  test.skip(!process.env.E2E_EMAIL, "Skipped: no E2E_EMAIL env var set");

  test("dashboard loads after login", async ({ page }) => {
    await loginAs(page, process.env.E2E_EMAIL!, process.env.E2E_PASSWORD!);
    await expect(page.locator("#nav-dashboard")).toBeVisible();
    await expect(page.locator("#nav-jobs")).toBeVisible();
  });

  test("nav links are visible", async ({ page }) => {
    await loginAs(page, process.env.E2E_EMAIL!, process.env.E2E_PASSWORD!);
    for (const nav of ["dashboard", "jobs", "stores", "billing", "settings", "backup", "import"]) {
      await expect(page.locator(`#nav-${nav}`)).toBeVisible();
    }
  });

  test("tour restart button is visible", async ({ page }) => {
    await loginAs(page, process.env.E2E_EMAIL!, process.env.E2E_PASSWORD!);
    await expect(page.locator("button[title='Replay tour']")).toBeVisible();
  });
});
