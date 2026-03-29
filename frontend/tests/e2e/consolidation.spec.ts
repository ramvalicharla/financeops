import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const entities = [
  {
    entity_id: "entity-001",
    entity_name: "Acme India",
    currency: "INR",
    fx_rate_to_inr: "1.00",
    reporting_period: "2026-03",
    is_included: true,
  },
  {
    entity_id: "entity-002",
    entity_name: "Acme US",
    currency: "USD",
    fx_rate_to_inr: "83.50",
    reporting_period: "2026-03",
    is_included: true,
  },
]

const summary = {
  period: "2026-03",
  base_currency: "INR" as const,
  consolidated_revenue: "4500000.00",
  consolidated_gross_profit: "1800000.00",
  consolidated_ebitda: "1200000.00",
  consolidated_net_profit: "900000.00",
  intercompany_eliminations: "75000.00",
  fx_translation_difference: "25000.00",
  entity_breakdown: [
    {
      entity_id: "entity-001",
      entity_name: "Acme India",
      currency: "INR",
      fx_rate: "1.00",
      revenue_local: "3000000.00",
      revenue_inr: "3000000.00",
      gross_profit_inr: "1200000.00",
      ebitda_inr: "850000.00",
      net_profit_inr: "620000.00",
    },
    {
      entity_id: "entity-002",
      entity_name: "Acme US",
      currency: "USD",
      fx_rate: "83.50",
      revenue_local: "18000.00",
      revenue_inr: "1503000.00",
      gross_profit_inr: "600000.00",
      ebitda_inr: "350000.00",
      net_profit_inr: "280000.00",
    },
  ],
}

test.describe("Consolidation page", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)

    await page.route("**/api/v1/consolidation/entities**", async (route) => {
      await fulfillJson(route, apiResponse(entities))
    })
    await page.route("**/api/v1/consolidation/fx-rates?**", async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          { currency: "INR", rate_to_inr: "1.00" },
          { currency: "USD", rate_to_inr: "83.50" },
        ]),
      )
    })
  })

  test("Consolidation page loads", async ({ page }) => {
    await page.route("**/api/v1/consolidation/summary", async (route) => {
      await fulfillJson(route, apiResponse(summary))
    })

    await page.goto("/consolidation")
    await expect(page.getByText("Acme India")).toBeVisible()
    await expect(page.getByText("Acme US")).toBeVisible()
    await expect(page.getByText("USD @")).toBeVisible()
  })

  test("Run consolidation", async ({ page }) => {
    await page.route("**/api/v1/consolidation/summary", async (route) => {
      await page.waitForTimeout(200)
      await fulfillJson(route, apiResponse(summary))
    })

    await page.goto("/consolidation")
    await page.getByRole("button", { name: "Run Consolidation" }).click()
    await expect(page.getByText("Consolidation Summary")).toBeVisible()
    await expect(page.getByText("Consolidated Revenue")).toBeVisible()
  })

  test("Entity breakdown drill-down", async ({ page }) => {
    await page.route("**/api/v1/consolidation/summary", async (route) => {
      await fulfillJson(route, apiResponse(summary))
    })

    await page.goto("/consolidation")
    await page.getByRole("button", { name: "Run Consolidation" }).click()
    await page.getByRole("button", { name: "Consolidated Revenue" }).click()
    await expect(page.getByText("Entity Breakdown")).toBeVisible()
    await expect(page.getByText("Acme India")).toBeVisible()
    await expect(page.getByText("Acme US")).toBeVisible()
  })

  test("Error state", async ({ page }) => {
    await page.route("**/api/v1/consolidation/summary", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "failed" },
          meta: { request_id: "req-con", timestamp: new Date().toISOString() },
        },
        500,
      )
    })

    await page.goto("/consolidation")
    await page.getByRole("button", { name: "Run Consolidation" }).click()
    await expect(page.getByText("Failed to run consolidation summary.")).toBeVisible()
    await expectNotCrashed(page)
  })
})
