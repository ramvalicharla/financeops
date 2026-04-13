import { expect, test } from "@playwright/test"
import { apiResponse, enableAuthBypassHeader, fulfillJson } from "./helpers/mocks"

// Helper to go through the 3-step login form and trigger the MFA backend response.
// Step 1: email → Continue | Step 2: password → Sign in | Step 3: inline OTP (no URL change)
async function triggerMfaChallenge(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.goto("/login")
  await page.getByLabel("Email").fill(email)
  await page.getByRole("button", { name: "Continue", exact: true }).click()
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  // Step 3 appears inline — wait for the OTP subtitle
  await expect(
    page.getByText("Enter the 6-digit code from your authenticator app."),
  ).toBeVisible()
}

test.describe("MFA security", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
  })

  test("Credentials never written to sessionStorage during MFA flow", async ({ page }) => {
    await page.route("**/api/v1/auth/login", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          requires_mfa: true,
          mfa_challenge_token: "challenge-token-123",
        }),
      )
    })

    await triggerMfaChallenge(page, "mfa.user@example.com", "SuperSecret123!")

    const storageState = await page.evaluate(() => {
      const legacyKeyEmpty = sessionStorage.getItem("MFA_SESSION_KEY") === null
      const keys = Object.keys(sessionStorage)
      const noMfaKeyNames = keys.every((k) => !k.toLowerCase().includes("mfa"))
      const values = keys.map((k) => sessionStorage.getItem(k) ?? "")
      return {
        legacyKeyEmpty,
        noMfaKeyNames,
        values,
      }
    })

    expect(storageState.legacyKeyEmpty).toBeTruthy()
    expect(storageState.noMfaKeyNames).toBeTruthy()
    expect(storageState.values.join(" ")).not.toContain("mfa.user@example.com")
    expect(storageState.values.join(" ")).not.toContain("SuperSecret123!")
  })

  test("Credentials are never written to localStorage during MFA challenge", async ({ page }) => {
    await page.route("**/api/v1/auth/login", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          requires_mfa: true,
          mfa_challenge_token: "challenge-token-abc",
        }),
      )
    })

    await triggerMfaChallenge(page, "secure.user@example.com", "NeverStoreThis123!")

    const storageState = await page.evaluate(() => {
      const keys = Object.keys(localStorage)
      const values = keys.map((k) => localStorage.getItem(k) ?? "")
      return { keys, values }
    })

    expect(storageState.keys.join(" ")).not.toContain("mfa")
    expect(storageState.values.join(" ")).not.toContain("secure.user@example.com")
    expect(storageState.values.join(" ")).not.toContain("NeverStoreThis123!")
  })

  test("MFA challenge token is not persisted in web storage", async ({ page }) => {
    await page.route("**/api/v1/auth/login", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          requires_mfa: true,
          mfa_challenge_token: "challenge-token-no-storage",
        }),
      )
    })

    await triggerMfaChallenge(page, "token.user@example.com", "DoNotPersist123!")

    const persisted = await page.evaluate(() => {
      const allValues = [
        ...Object.keys(sessionStorage).map((k) => sessionStorage.getItem(k) ?? ""),
        ...Object.keys(localStorage).map((k) => localStorage.getItem(k) ?? ""),
      ].join(" ")
      return allValues.includes("challenge-token-no-storage")
    })

    expect(persisted).toBeFalsy()
  })
})
