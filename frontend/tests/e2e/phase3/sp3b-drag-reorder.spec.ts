/**
 * SP-3B — Drag-to-reorder with moduleOrder store persistence
 *
 * Covers: drag handle visible per row, localStorage persistence chain,
 * novel backend tabs appended after stored order.
 * Live keyboard reorder (Space → ArrowDown × 2 → Space) is tested in
 * sp3b-keyboard-manual.spec.ts.
 */
import { expect, test, type Page } from "@playwright/test"
import * as path from "path"
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
const STORAGE_KEY = "finqor:module-order:v1"

const THREE_TABS = [
  { workspace_key: "dashboard", workspace_name: "Dashboard", href: "/dashboard", match_prefixes: ["/dashboard"], module_codes: [] },
  { workspace_key: "accounting", workspace_name: "Accounting", href: "/accounting", match_prefixes: ["/accounting"], module_codes: [] },
  { workspace_key: "reconciliation", workspace_name: "Reconciliation", href: "/reconciliation", match_prefixes: ["/reconciliation"], module_codes: [] },
]

const mockThreeTabs = async (page: Page) => {
  await page.route("**/api/v1/platform/control-plane/context**", async (route) => {
    await fulfillJson(
      route,
      apiResponse({
        tenant_id: "tenant-001",
        tenant_slug: "acme",
        workspace_tabs: THREE_TABS,
        current_organisation: { organisation_id: "org-001", organisation_name: "Acme", source: "mock" },
        current_entity: { entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd", source: "mock" },
        available_entities: [{ entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd" }],
        current_module: { module_key: "dashboard", module_name: "Dashboard", module_code: "dashboard", source: "mock" },
        enabled_modules: [],
        current_period: { period_label: "Apr 2026", fiscal_year: 2026, period_number: 4, source: "mock", period_id: "period-2026-04", status: "open" },
      }),
    )
  })
}

test.describe("SP-3B — Drag-to-reorder", () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test so store starts empty
    await page.addInitScript(() => {
      localStorage.removeItem("finqor:module-order:v1")
    })
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
    await mockThreeTabs(page)
    await page.goto("/dashboard")
    await page.waitForLoadState("networkidle")
  })

  test("each active module row shows a drag handle button", async ({ page }) => {
    await openModuleManager(page)
    const list = page.getByRole("list", { name: "Active modules" })
    await expect(list).toBeVisible()
    const handles = list.getByRole("button", { name: /Drag to reorder/ })
    await expect(handles).toHaveCount(THREE_TABS.length)
    await page.screenshot({
      path: `${SCREENSHOTS}/sp3b-drag-handles.png`,
      fullPage: false,
    })
    await expectNotCrashed(page)
  })

  test("pre-seeded localStorage order is reflected in dialog item order", async ({ page }) => {
    // Seed a custom order: reconciliation first, then dashboard, then accounting
    const seededOrder = ["reconciliation", "dashboard", "accounting"]
    await page.addInitScript(
      ({ key, order }) => {
        localStorage.setItem(key, JSON.stringify({ state: { order }, version: 0 }))
      },
      { key: STORAGE_KEY, order: seededOrder },
    )

    await openModuleManager(page)
    const list = page.getByRole("list", { name: "Active modules" })
    await expect(list).toBeVisible()
    const items = list.locator("li")

    await expect(items.first()).toContainText("Reconciliation")
    await expect(items.nth(1)).toContainText("Dashboard")
    await expect(items.nth(2)).toContainText("Accounting")
    await page.screenshot({
      path: `${SCREENSHOTS}/sp3b-localStorage-persisted.png`,
      fullPage: false,
    })
  })

  test("novel backend tab appended after stored order", async ({ page }) => {
    // Seed localStorage with order that omits 'erp' (a novel key)
    await page.addInitScript((key) => {
      const state = { state: { order: ["dashboard", "accounting"] }, version: 0 }
      localStorage.setItem(key, JSON.stringify(state))
    }, STORAGE_KEY)

    // Override context to include 'erp' as a new tab
    await page.route("**/api/v1/platform/control-plane/context**", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          tenant_id: "tenant-001",
          tenant_slug: "acme",
          workspace_tabs: [
            ...THREE_TABS.slice(0, 2),
            { workspace_key: "erp", workspace_name: "ERP", href: "/erp", match_prefixes: ["/erp"], module_codes: [] },
          ],
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
    const list = page.getByRole("list", { name: "Active modules" })
    const items = list.locator("li")
    // Stored order: Dashboard, Accounting. Novel: ERP → appended last
    await expect(items.first()).toContainText("Dashboard")
    await expect(items.nth(1)).toContainText("Accounting")
    await expect(items.nth(2)).toContainText("ERP")
  })

  test("page does not crash when module order store is empty", async ({ page }) => {
    await openModuleManager(page)
    await expect(page.getByRole("list", { name: "Active modules" })).toBeVisible()
    await expectNotCrashed(page)
  })
})
