import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test("login page loads", async ({ page }) => {
    await page.goto("/en/login");
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[type='password']")).toBeVisible();
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await page.goto("/en/login");
    await page.fill("input[type='email']", "wrong@example.com");
    await page.fill("input[type='password']", "wrongpass");
    await page.click("button[type='submit']");
    await expect(page.locator("text=Invalid email or password").first()).toBeVisible({ timeout: 5000 });
  });

  test("register page loads", async ({ page }) => {
    await page.goto("/en/register");
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[type='password']")).toBeVisible();
  });

  test("unauthenticated user redirected to login", async ({ page }) => {
    await page.goto("/en/dashboard");
    await expect(page).toHaveURL(/login/, { timeout: 5000 });
  });
});
