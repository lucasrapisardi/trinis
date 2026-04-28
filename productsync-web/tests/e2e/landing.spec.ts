import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test("should load landing page at /", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Trinis|ProductSync/i);
    await expect(page.locator("text=Entrar").first()).toBeVisible();
  });

  test("should have CTA button", async ({ page }) => {
    await page.goto("/");
    const cta = page.locator("text=Começar grátis").first();
    await expect(cta).toBeVisible();
  });

  test("Entrar link goes to login", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Entrar");
    await expect(page).toHaveURL(/login/);
  });
});
