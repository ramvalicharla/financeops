import { expect, test } from "@playwright/test"

test.describe("Registration flow", () => {
  test("registration page loads", async ({ page }) => {
    await page.goto("/register")
    await expect(page.getByText("Create your Finqor account")).toBeVisible()
  })

  test("registration form validates required fields", async ({ page }) => {
    await page.goto("/register")
    await page.getByRole("button", { name: "Create Account" }).click()
    await expect(page.getByText("Full name is required")).toBeVisible()
  })

  test("login page has forgot password link", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Forgot password?")).toBeVisible()
  })

  test("login page has register link", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Create one free")).toBeVisible()
  })
})

test.describe("Forgot password flow", () => {
  test("forgot password page loads", async ({ page }) => {
    await page.goto("/forgot-password")
    await expect(page.getByText("Reset your password")).toBeVisible()
  })

  test("submitting email shows confirmation", async ({ page }) => {
    await page.goto("/forgot-password")
    await page.fill("input[type=email]", "test@example.com")
    await page.getByRole("button", { name: "Send Reset Link" }).click()
    await expect(page.getByText("Check your inbox")).toBeVisible()
  })
})

test.describe("MFA setup flow", () => {
  test("mfa setup page loads", async ({ page }) => {
    await page.goto("/mfa/setup")
    await expect(page.getByText("Set Up Two-Factor Authentication")).toBeVisible()
  })
})

test.describe("Landing page", () => {
  test("landing page shows for unauthenticated user", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText("Enterprise finance platform for the India mid-market")).toBeVisible()
  })

  test("landing page has sign in and register links", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible()
    await expect(page.getByRole("link", { name: "Start free trial" }).first()).toBeVisible()
  })
})
