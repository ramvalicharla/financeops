import { expect, type Page, type Route } from "@playwright/test"

export function apiResponse<T>(data: T) {
  return {
    data,
    error: null,
    meta: { request_id: "test-req-id", timestamp: new Date().toISOString() },
  }
}

export async function mockSession(page: Page) {
  await page.route("**/api/v1/platform/entities**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse([
          {
            id: "entity-001",
            entity_code: "ACME-LTD",
            entity_name: "Acme Ltd",
            organisation_id: "org-001",
          },
          {
            id: "entity-002",
            entity_code: "ACME-HOLD",
            entity_name: "Acme Holdings",
            organisation_id: "org-001",
          },
        ]),
      ),
    })
  })

  await page.route("**/api/v1/platform/control-plane/context**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          workspace_tabs: [
            {
              workspace_key: "financials",
              workspace_name: "Financials",
              href: "/dashboard",
              match_prefixes: ["/dashboard", "/sync"],
              module_codes: ["sync"],
            },
          ],
          current_organisation: {
            organisation_id: "org-001",
            organisation_name: "Acme",
            source: "mock",
          },
          current_entity: {
            entity_id: "entity-001",
            entity_code: "ACME-LTD",
            entity_name: "Acme Ltd",
            source: "mock",
          },
          available_entities: [
            {
              entity_id: "entity-001",
              entity_code: "ACME-LTD",
              entity_name: "Acme Ltd",
            },
            {
              entity_id: "entity-002",
              entity_code: "ACME-HOLD",
              entity_name: "Acme Holdings",
            },
          ],
          current_module: {
            module_key: "sync",
            module_name: "Sync",
            module_code: "sync",
            source: "mock",
          },
          enabled_modules: [
            {
              module_id: "mod-sync",
              module_code: "sync",
              module_name: "Sync",
              engine_context: "financials",
              is_financial_impacting: false,
              effective_from: "2026-01-01",
            },
          ],
          current_period: {
            period_label: "Apr 2026",
            fiscal_year: 2026,
            period_number: 4,
            source: "mock",
            period_id: "period-2026-04",
            status: "open",
          },
        }),
      ),
    })
  })

  await page.route("**/api/v1/tenants/display-preferences**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          effective_scale: "INR",
          user_override: null,
          tenant_default: "INR",
          currency: "INR",
          locale: "en-IN",
          scale_label: "INR",
        }),
      ),
    })
  })

  await page.route("**/api/v1/notifications/unread-count**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(apiResponse({ count: 0 })),
    })
  })

  await page.route("**/api/v1/tenants/me**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          tenant_id: "tenant-001",
          display_name: "Acme",
          tenant_type: "customer",
          country: "IN",
          timezone: "Asia/Kolkata",
          status: "active",
          org_setup_complete: true,
          org_setup_step: 7,
          coa_status: "uploaded",
          onboarding_score: 100,
          created_at: "2026-01-01T00:00:00Z",
        }),
      ),
    })
  })

  await page.route("**/api/v1/locations?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          items: [],
          total: 0,
          skip: 0,
          limit: 200,
          has_more: false,
        }),
      ),
    })
  })

  await page.route("**/api/v1/billing/entitlements/current", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        apiResponse({
          items: [
            "erp_integration",
            "reconciliation",
            "reconciliation_bridge",
            "payroll_gl_reconciliation",
            "mis_manager",
            "board_pack_generator",
            "custom_report_builder",
            "scheduled_delivery",
            "anomaly_ui",
            "multi_entity_consolidation",
          ].map((feature_name, index) => ({
            id: `entitlement-${index + 1}`,
            feature_name,
            access_type: "boolean",
            effective_limit: null,
            source: "plan",
            source_reference_id: "plan-pro",
            metadata: {},
          })),
        }),
      ),
    })
  })

  await page.route("**/api/auth/session**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "user-001",
          email: "test@acme.com",
          name: "Test User",
          role: "finance_leader",
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          org_setup_complete: true,
          org_setup_step: 7,
          coa_status: "uploaded",
          onboarding_score: 100,
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

  await page.route("**/api/auth/providers**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        credentials: {
          id: "credentials",
          name: "credentials",
          type: "credentials",
          signinUrl: "http://localhost:3010/api/auth/signin/credentials",
          callbackUrl: "http://localhost:3010/api/auth/callback/credentials",
        },
      }),
    })
  })

  await page.route("**/api/auth/signout**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ url: "/login" }),
    })
  })
}

export async function mockCSRF(page: Page) {
  await page.route("**/api/auth/csrf**", async (route) => {
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
          role: "finance_leader",
          tenant: {
            tenant_id: "tenant-001",
            display_name: "Acme",
            slug: "acme",
            org_setup_complete: true,
            org_setup_step: 7,
            coa_status: "uploaded",
            onboarding_score: 100,
          },
          entity_roles: [
            { entity_id: "entity-001", entity_name: "Acme Ltd", role: "admin" },
            {
              entity_id: "entity-002",
              entity_name: "Acme Holdings",
              role: "accountant",
            },
          ],
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

/**
 * Variant of mockSession that sets role: "auditor" (maps to tenant_viewer via ROLE_ALIASES).
 * Also sets x-e2e-role header so the server-rendered DashboardLayout passes role="auditor"
 * as the userRole prop to the Sidebar (the fallback user in layout.tsx respects this header).
 */
export async function mockAuditorSession(page: Page): Promise<void> {
  await page.context().setExtraHTTPHeaders({
    "x-e2e-auth-bypass": "true",
    "x-tenant-slug": "acme",
    "x-e2e-role": "auditor",
  })
  await mockSession(page)
  await page.route("**/api/auth/session**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "user-001",
          email: "auditor@acme.com",
          name: "Audit User",
          role: "auditor",
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          org_setup_complete: true,
          org_setup_step: 7,
          coa_status: "uploaded",
          onboarding_score: 100,
          entity_roles: [
            { entity_id: "entity-001", entity_name: "Acme Ltd", role: "viewer" },
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
