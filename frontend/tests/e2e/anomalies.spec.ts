import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const baseAlert = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "tenant-001",
  alert_type: "ANOM_REVENUE_SPIKE",
  rule_code: "ANOM_REVENUE_SPIKE",
  severity: "HIGH",
  category: "profitability",
  detected_at: "2026-03-21T12:00:00Z",
  alert_status: "OPEN",
  snoozed_until: null,
  resolved_at: null,
  escalated_at: null,
  status_note: null,
  status_updated_by: null,
  run_id: "22222222-2222-2222-2222-222222222222",
  line_no: 1,
  anomaly_code: "ANOM_REVENUE_SPIKE",
  anomaly_name: "Revenue Spike",
  anomaly_score: "0.920000",
  confidence_score: "0.880000",
  persistence_classification: "first_detected",
  correlation_flag: false,
  materiality_elevated: true,
  risk_elevated: false,
  board_flag: true,
  source_summary_json: {},
  source_table: "gl_entries",
  source_row_id: "1234",
  created_by: "33333333-3333-3333-3333-333333333333",
  created_at: "2026-03-21T12:00:00Z",
}

const lowSeverityAlert = {
  ...baseAlert,
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  alert_type: "ANOM_LOW",
  rule_code: "ANOM_LOW",
  anomaly_code: "ANOM_LOW",
  anomaly_name: "Low Alert",
  severity: "LOW",
}

test.describe("Anomalies pages", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Page loads and filter bar is visible", async ({ page }) => {
    await page.route("**/api/v1/anomalies**", async (route) => {
      await fulfillJson(route, apiResponse([baseAlert]))
    })

    await page.goto("/anomalies")

    await expect(
      page.locator("main").getByRole("heading", { name: "Anomaly Detection" }),
    ).toBeVisible()
    await expect(page.locator("#anomaly-severity-filter")).toBeVisible()
    await expect(page.locator("#anomaly-category-filter")).toBeVisible()
    await expect(page.locator("#anomaly-status-filter")).toBeVisible()
  })

  test("Severity filter changes displayed alerts", async ({ page }) => {
    await page.route("**/api/v1/anomalies**", async (route) => {
      const url = new URL(route.request().url())
      const severity = url.searchParams.get("severity")
      if (severity === "high") {
        await fulfillJson(route, apiResponse([baseAlert]))
        return
      }
      await fulfillJson(route, apiResponse([baseAlert, lowSeverityAlert]))
    })

    await page.goto("/anomalies")
    await expect(page.getByText("ANOM_REVENUE_SPIKE")).toBeVisible()
    await expect(page.getByText("ANOM_LOW")).toBeVisible()

    await page.locator("#anomaly-severity-filter").selectOption("HIGH")
    await expect(page.getByText("ANOM_REVENUE_SPIKE")).toBeVisible()
    await expect(page.getByText("ANOM_LOW")).toHaveCount(0)
  })

  test("Resolve action calls PATCH and status badge updates", async ({ page }) => {
    let status: "OPEN" | "RESOLVED" = "OPEN"
    let patchCount = 0

    await page.route("**/api/v1/anomalies**", async (route) => {
      const request = route.request()
      const url = new URL(request.url())

      if (request.method() === "PATCH" && url.pathname.endsWith("/status")) {
        patchCount += 1
        status = "RESOLVED"
        await fulfillJson(route, apiResponse({ ...baseAlert, alert_status: "RESOLVED" }))
        return
      }

      if (request.method() === "GET") {
        const statusFilter = url.searchParams.get("status") ?? "OPEN"
        if (statusFilter === "RESOLVED" && status === "RESOLVED") {
          await fulfillJson(route, apiResponse([{ ...baseAlert, alert_status: "RESOLVED" }]))
          return
        }
        if (statusFilter === "OPEN" && status === "OPEN") {
          await fulfillJson(route, apiResponse([baseAlert]))
          return
        }
        await fulfillJson(route, apiResponse([]))
        return
      }

      await route.continue()
    })

    await page.goto("/anomalies")
    await expect(page.getByRole("button", { name: "Resolve" }).first()).toBeVisible()

    await page.getByRole("button", { name: "Resolve" }).first().click()
    await expect.poll(() => patchCount).toBe(1)

    await page.locator("#anomaly-status-filter").selectOption("RESOLVED")
    await expect(page.getByRole("table").getByText("RESOLVED")).toBeVisible()
  })
})
