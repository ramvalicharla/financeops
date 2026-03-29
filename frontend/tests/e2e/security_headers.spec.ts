import { expect, test } from "@playwright/test"

test.describe("Security headers", () => {
  test("X-Content-Type-Options: nosniff on every response", async ({ page }) => {
    const response = await page.goto("/login")
    const header = response?.headers()["x-content-type-options"]
    expect(header).toBe("nosniff")
  })

  test("X-Frame-Options: DENY prevents clickjacking", async ({ page }) => {
    const response = await page.goto("/login")
    const header = response?.headers()["x-frame-options"]
    expect(header).toBe("DENY")
  })

  test("Referrer-Policy is set on every response", async ({ page }) => {
    const response = await page.goto("/login")
    const header = response?.headers()["referrer-policy"]
    expect(header).toBe("strict-origin-when-cross-origin")
  })

  test("Content-Security-Policy header is present", async ({ page }) => {
    const response = await page.goto("/login")
    const header = response?.headers()["content-security-policy"]
    expect(header).toBeTruthy()
    expect(header).toContain("default-src 'self'")
    expect(header).toContain("frame-ancestors 'none'")
  })

  test("Strict-Transport-Security header is set", async ({ page }) => {
    const response = await page.goto("/login")
    const header = response?.headers()["strict-transport-security"]
    expect(header).toContain("max-age=31536000")
    expect(header).toContain("includeSubDomains")
  })
})

