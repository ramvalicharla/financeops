import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const dashboardPayload = (period: string, revenue: string) => ({
  entity_id: "entity-001",
  period,
  previous_period: "2026-02",
  revenue,
  gross_profit: "450000.00",
  ebitda: "300000.00",
  net_profit: "210000.00",
  revenue_change_pct: "5.20",
  gross_profit_change_pct: "4.10",
  ebitda_change_pct: "3.80",
  net_profit_change_pct: "2.20",
  line_items: [
    {
      line_item_id: "heading-1",
      label: "Operating Revenue",
      current_value: "1000000.00",
      previous_value: "950000.00",
      variance: "50000.00",
      variance_pct: "5.26",
      is_heading: true,
      indent_level: 0,
    },
    {
      line_item_id: "line-1",
      label: "Domestic Sales",
      current_value: "700000.00",
      previous_value: "680000.00",
      variance: "20000.00",
      variance_pct: "2.94",
      is_heading: false,
      indent_level: 1,
    },
  ],
  chart_data: [
    { period: "2026-01", label: "Jan 26", revenue: "900000.00", gross_profit: "420000.00", ebitda: "280000.00" },
    { period: "2026-02", label: "Feb 26", revenue: "950000.00", gross_profit: "440000.00", ebitda: "295000.00" },
    { period: "2026-03", label: "Mar 26", revenue, gross_profit: "450000.00", ebitda: "300000.00" },
  ],
})

test.describe("MIS dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)

    await page.route("**/api/v1/mis/periods?**", async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          { period: "2026-03", label: "March 2026" },
          { period: "2026-02", label: "February 2026" },
        ]),
      )
    })
  })

  test("MIS dashboard loads", async ({ page }) => {
    await page.route("**/api/v1/mis/dashboard?**", async (route) => {
      const url = new URL(route.request().url())
      const period = url.searchParams.get("period") ?? "2026-03"
      await fulfillJson(route, apiResponse(dashboardPayload(period, "1000000.00")))
    })

    await page.goto("/mis")
    await page.getByLabel("Entity").selectOption("entity-001")
    await expect(page.getByText("Revenue")).toBeVisible()
    await expect(page.getByText("Gross Profit")).toBeVisible()
    await expect(page.getByText("EBITDA")).toBeVisible()
    await expect(page.getByText("Net Profit")).toBeVisible()
    await expect(page.locator("svg.recharts-surface")).toBeVisible()
    await expect(page.getByText("Operating Revenue")).toBeVisible()
  })

  test("Period change updates data", async ({ page }) => {
    await page.route("**/api/v1/mis/dashboard?**", async (route) => {
      const url = new URL(route.request().url())
      const period = url.searchParams.get("period") ?? "2026-03"
      const revenue = period === "2026-02" ? "900000.00" : "1000000.00"
      await fulfillJson(route, apiResponse(dashboardPayload(period, revenue)))
    })

    await page.goto("/mis")
    await page.getByLabel("Entity").selectOption("entity-001")
    await expect(page.getByText("₹10,00,000.00")).toBeVisible()
    await page.getByLabel("Period").selectOption("2026-02")
    await expect(page.getByText("₹9,00,000.00")).toBeVisible()
  })

  test("Loading state", async ({ page }) => {
    await page.route("**/api/v1/mis/dashboard?**", async (route) => {
      await page.waitForTimeout(500)
      const url = new URL(route.request().url())
      const period = url.searchParams.get("period") ?? "2026-03"
      await fulfillJson(route, apiResponse(dashboardPayload(period, "1000000.00")))
    })

    await page.goto("/mis")
    await page.getByLabel("Entity").selectOption("entity-001")
    await expect(page.locator(".animate-pulse").first()).toBeVisible()
  })

  test("Error state", async ({ page }) => {
    await page.route("**/api/v1/mis/dashboard?**", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "failed" },
          meta: { request_id: "req-mis", timestamp: new Date().toISOString() },
        },
        500,
      )
    })

    await page.goto("/mis")
    await page.getByLabel("Entity").selectOption("entity-001")
    await expect(page.getByText("Failed to load MIS dashboard data.")).toBeVisible()
    await expectNotCrashed(page)
  })
})
