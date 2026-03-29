import { expect, type Page, type Route } from "@playwright/test"

export function apiResponse<T>(data: T) {
  return {
    data,
    error: null,
    meta: { request_id: "test-req-id", timestamp: new Date().toISOString() },
  }
}

export async function mockSession(page: Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "user-001",
          email: "test@acme.com",
          name: "Test User",
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          org_setup_complete: true,
          org_setup_step: 7,
          entity_roles: [
            { entity_id: "entity-001", entity_name: "Acme Ltd", role: "admin" },
            {
              entity_id: "entity-002",
              entity_name: "Acme Holdings",
              role: "accountant",
            },
          ],
        },
        access_token: createMockJwt(3600),
        refresh_token: "mock-refresh-token",
        access_token_expires_at: Date.now() + 3600 * 1000,
        expires: "2099-01-01T00:00:00.000Z",
      }),
    })
  })
}

export async function mockCSRF(page: Page) {
  await page.route("**/api/auth/csrf", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ csrfToken: "mock-csrf-token" }),
    })
  })
}

export async function enableAuthBypassHeader(page: Page) {
  await page.context().setExtraHTTPHeaders({
    "x-e2e-auth-bypass": "true",
    "x-tenant-slug": "acme",
  })
}

export function createMockJwt(expiryInSeconds: number): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString(
    "base64url",
  )
  const payload = Buffer.from(
    JSON.stringify({
      exp: Math.floor(Date.now() / 1000) + expiryInSeconds,
      sub: "user-001",
    }),
  ).toString("base64url")
  return `${header}.${payload}.signature`
}

export async function mockAuthSuccess(page: Page) {
  const accessToken = createMockJwt(3600)
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          access_token: accessToken,
          refresh_token: "refresh-token",
          token_type: "bearer",
        }),
      ),
    })
  })

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          user_id: "user-001",
          email: "test@acme.com",
          full_name: "Test User",
          role: "admin",
          tenant: {
            tenant_id: "tenant-001",
            display_name: "Acme",
            org_setup_complete: true,
            org_setup_step: 7,
          },
        }),
      ),
    })
  })

  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          access_token: createMockJwt(3600),
          refresh_token: "refresh-token-2",
          token_type: "bearer",
        }),
      ),
    })
  })
}

export async function authenticate(page: Page) {
  await mockCSRF(page)
  await mockSession(page)
  await mockAuthSuccess(page)
  await page.goto("/login")
  await page.getByLabel("Email").fill("test@acme.com")
  await page.getByLabel("Password").fill("Secret123!")
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL("**/sync")
}

export async function fulfillJson(
  route: Route,
  data: unknown,
  status = 200,
): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  })
}

export async function expectNotCrashed(page: Page) {
  await expect(page.locator("body")).toBeVisible()
}
