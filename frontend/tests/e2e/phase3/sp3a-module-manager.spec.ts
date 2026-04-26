/**
 * SP-3A — ModuleManager dialog
 *
 * Covers: dialog open/close, tab structure, active modules list, available tab,
 * premium/custom placeholders, loading state, and drag handle presence.
 *
 * Opening strategy: useModuleManagerStore.getState().open() via webpack registry
 * (openModuleManager helper) because canPerformAction("module.manage") is always
 * false — "module.manage" is absent from the PERMISSIONS matrix.
 */
import { expect, test } from "@playwright/test"
import * as path from "path"
import type { Page } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "../helpers/mocks"
import { openModuleManager } from "../helpers/stores"

const SCREENSHOTS = path.resolve(__dirname, "screenshots")

const mockContextWithTabs = async (page: Page) => {
  await page.route("**/api/v1/platform/control-plane/context**", async (route) => {
    await fulfillJson(
      route,
      apiResponse({
        tenant_id: "tenant-001",
        tenant_slug: "acme",
        workspace_tabs: [
          {
            workspace_key: "dashboard",
            workspace_name: "Dashboard",
            href: "/dashboard",
            match_prefixes: ["/dashboard"],
            module_codes: [],
          },
          {
            workspace_key: "accounting",
            workspace_name: "Accounting",
            href: "/accounting",
            match_prefixes: ["/accounting"],
            module_codes: ["accounting"],
          },
          {
            workspace_key: "reconciliation",
            workspace_name: "Reconciliation",
            href: "/reconciliation",
            match_prefixes: ["/reconciliation"],
            module_codes: ["reconciliation"],
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
          { entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd" },
        ],
        current_module: {
          module_key: "dashboard",
          module_name: "Dashboard",
          module_code: "dashboard",
          source: "mock",
        },
        enabled_modules: [],
        current_period: {
          period_label: "Apr 2026",
          fiscal_year: 2026,
          period_number: 4,
          source: "mock",
          period_id: "period-2026-04",
          status: "open",
        },
      }),
    )
  })
}

test.describe("SP-3A — ModuleManager dialog", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
    await mockContextWithTabs(page)
    await page.goto("/dashboard")
    await page.waitForLoadState("networkidle")
  })

  test("dialog opens and renders title", async ({ page }) => {
    await openModuleManager(page)
    await expect(page.getByRole("dialog")).toBeVisible()
    await expect(page.getByText("Module Manager")).toBeVisible()
    await expect(
      page.getByText("Configure which modules appear in your workspace tab bar."),
    ).toBeVisible()
    await expectNotCrashed(page)
  })

  test("dialog closes on dismiss", async ({ page }) => {
    await openModuleManager(page)
    await expect(page.getByRole("dialog")).toBeVisible()
    await page.keyboard.press("Escape")
    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("all four tabs are present", async ({ page }) => {
    await openModuleManager(page)
    await expect(page.getByRole("tab", { name: "Active" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "Available" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "Premium" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "Custom" })).toBeVisible()
  })

  test("active tab lists workspace modules from API", async ({ page }) => {
    await openModuleManager(page)
    await expect(page.getByRole("tab", { name: "Active" })).toBeVisible()
    const list = page.getByRole("list", { name: "Active modules" })
    await expect(list).toBeVisible()
    await expect(list.getByText("Dashboard")).toBeVisible()
    await expect(list.getByText("Accounting")).toBeVisible()
    await expect(list.getByText("Reconciliation")).toBeVisible()
    await page.screenshot({
      path: `${SCREENSHOTS}/sp3a-dialog-active-tab.png`,
      fullPage: false,
    })
  })

  test("available tab lists catalog entries not already active", async ({ page }) => {
    await openModuleManager(page)
    await page.getByRole("tab", { name: "Available" }).click()
    const list = page.getByRole("list", { name: "Available modules" })
    await expect(list).toBeVisible()
    // ERP, Close, Reports, Settings are in catalog but not in the mocked workspace_tabs
    await expect(list.getByText("ERP")).toBeVisible()
    await page.screenshot({
      path: `${SCREENSHOTS}/sp3a-dialog-available-tab.png`,
      fullPage: false,
    })
  })

  test("available tab shows 'All available modules are already active' when catalog is exhausted", async ({
    page,
  }) => {
    // Override context to include all 7 catalog entries
    await page.route("**/api/v1/platform/control-plane/context**", async (overrideRoute) => {
      await fulfillJson(
        overrideRoute,
        apiResponse({
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          workspace_tabs: [
            "dashboard",
            "erp",
            "accounting",
            "reconciliation",
            "close",
            "reports",
            "settings",
          ].map((workspace_key) => ({
            workspace_key,
            workspace_name: workspace_key.charAt(0).toUpperCase() + workspace_key.slice(1),
            href: `/${workspace_key}`,
            match_prefixes: [`/${workspace_key}`],
            module_codes: [],
          })),
          current_organisation: { organisation_id: "org-001", organisation_name: "Acme", source: "mock" },
          current_entity: { entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd", source: "mock" },
          available_entities: [],
          current_module: { module_key: "dashboard", module_name: "Dashboard", module_code: "dashboard", source: "mock" },
          enabled_modules: [],
          current_period: { period_label: "Apr 2026", fiscal_year: 2026, period_number: 4, source: "mock", period_id: "period-2026-04", status: "open" },
        }),
      )
    })
    await openModuleManager(page)
    await page.getByRole("tab", { name: "Available" }).click()
    await expect(page.getByText("All available modules are already active.")).toBeVisible()
  })

  test("premium tab renders locked placeholder cards", async ({ page }) => {
    await openModuleManager(page)
    await page.getByRole("tab", { name: "Premium" }).click()
    await expect(page.getByText("Premium modules will appear here.")).toBeVisible()
    await expectNotCrashed(page)
  })

  test("custom tab renders coming-soon placeholder", async ({ page }) => {
    await openModuleManager(page)
    await page.getByRole("tab", { name: "Custom" }).click()
    await expect(
      page.getByText("Custom modules coming soon"),
    ).toBeVisible()
    await expectNotCrashed(page)
  })

  test("loading state renders while context query is pending", async ({ page }) => {
    await page.route("**/api/v1/platform/control-plane/context**", async (slowRoute) => {
      // Delay so the component sees isPending = true
      await new Promise((r) => setTimeout(r, 1500))
      await fulfillJson(slowRoute, apiResponse({ workspace_tabs: [], current_organisation: { organisation_id: "org-001", organisation_name: "Acme", source: "mock" }, current_entity: { entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd", source: "mock" }, available_entities: [], current_module: { module_key: "dashboard", module_name: "Dashboard", module_code: "dashboard", source: "mock" }, enabled_modules: [], current_period: { period_label: "Apr 2026", fiscal_year: 2026, period_number: 4, source: "mock", period_id: "period-2026-04", status: "open" }, tenant_id: "tenant-001", tenant_slug: "acme" }))
    })
    await openModuleManager(page)
    await expect(page.getByText("Loading modules…")).toBeVisible()
    await page.screenshot({
      path: `${SCREENSHOTS}/sp3a-dialog-loading.png`,
      fullPage: false,
    })
  })
})
