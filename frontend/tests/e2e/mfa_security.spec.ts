import { expect, test } from "@playwright/test"
import { apiResponse, enableAuthBypassHeader, fulfillJson } from "./helpers/mocks"

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

    await page.goto("/login")
    await page.getByLabel("Email").fill("mfa.user@example.com")
    await page.getByLabel("Password").fill("SuperSecret123!")
    await page.getByRole("button", { name: "Sign in" }).click()
    await page.waitForURL("**/mfa?challenge=**")

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

    await page.goto("/login")
    await page.getByLabel("Email").fill("secure.user@example.com")
    await page.getByLabel("Password").fill("NeverStoreThis123!")
    await page.getByRole("button", { name: "Sign in" }).click()
    await page.waitForURL("**/mfa?challenge=**")

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

    await page.goto("/login")
    await page.getByLabel("Email").fill("token.user@example.com")
    await page.getByLabel("Password").fill("DoNotPersist123!")
    await page.getByRole("button", { name: "Sign in" }).click()
    await page.waitForURL("**/mfa?challenge=**")

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
