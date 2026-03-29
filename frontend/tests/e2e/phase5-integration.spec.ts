import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const boardPackDefinition = {
  id: "def-1",
  tenant_id: "tenant-001",
  name: "Monthly Board Pack",
  description: "Default definition",
  section_types: ["PROFIT_AND_LOSS", "BALANCE_SHEET"],
  entity_ids: ["11111111-1111-4111-8111-111111111111"],
  period_type: "MONTHLY",
  config: {},
  created_by: "user-001",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  is_active: true,
}

const reportDefinition = {
  id: "report-def-1",
  tenant_id: "tenant-001",
  name: "Monthly Report",
  description: "Custom report",
  metric_keys: ["mis.kpi.revenue"],
  filter_config: {
    conditions: [],
    period_start: "2024-03-01",
    period_end: "2024-03-31",
    entity_ids: [],
    account_codes: [],
    tags: [],
    amount_min: null,
    amount_max: null,
  },
  group_by: [],
  sort_config: { field: "mis.kpi.revenue", direction: "ASC" },
  export_formats: ["CSV", "EXCEL", "PDF"],
  config: {},
  created_by: "user-001",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  is_active: true,
}

const reportMetric = {
  key: "mis.kpi.revenue",
  label: "Revenue",
  source_table: "metric_results",
  source_column: "revenue",
  data_type: "decimal",
  engine: "mis",
}

const schedule = {
  id: "sched-1",
  tenant_id: "tenant-001",
  name: "Weekly Board Pack",
  description: "Weekly delivery",
  schedule_type: "BOARD_PACK",
  source_definition_id: "def-1",
  cron_expression: "0 8 * * 1",
  timezone: "UTC",
  recipients: [{ type: "EMAIL", address: "ops@example.com" }],
  export_format: "PDF",
  is_active: true,
  last_triggered_at: null,
  next_run_at: "2026-03-24T08:00:00Z",
  config: {},
  created_by: "user-001",
  created_at: "2026-03-21T10:00:00Z",
  updated_at: "2026-03-21T10:00:00Z",
}

const anomalyAlert = {
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

test.describe("Phase 5 cross-feature integration", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Full navigation across all Phase 5 pages", async ({ page }) => {
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/board-packs/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/reports/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/delivery/schedules**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/delivery/logs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/anomalies/thresholds", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/anomalies**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/board-pack")
    await expect(page.locator("main").getByRole("heading", { name: "Board Packs" })).toBeVisible()

    await page.goto("/reports")
    await expect(page.locator("main").getByRole("heading", { name: "Custom Reports" })).toBeVisible()

    await page.goto("/scheduled-delivery")
    await expect(
      page.locator("main").getByRole("heading", { name: "Scheduled Delivery" }),
    ).toBeVisible()

    await page.goto("/scheduled-delivery/logs")
    await expect(page.locator("main").getByRole("heading", { name: "Delivery Logs" })).toBeVisible()

    await page.goto("/anomalies")
    await expect(
      page.locator("main").getByRole("heading", { name: "Anomaly Detection" }),
    ).toBeVisible()

    await page.goto("/anomalies/thresholds")
    await expect(
      page.locator("main").getByRole("heading", { name: "Anomaly Thresholds" }),
    ).toBeVisible()
  })

  test("Board pack COMPLETE run shows enabled download buttons", async ({ page }) => {
    const runId = "run-complete-1"

    await page.route(`**/api/v1/board-packs/runs/${runId}`, async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          id: runId,
          tenant_id: "tenant-001",
          definition_id: boardPackDefinition.id,
          period_start: "2024-03-01",
          period_end: "2024-03-31",
          status: "COMPLETE",
          triggered_by: "user-001",
          started_at: "2026-03-01T10:00:00Z",
          completed_at: "2026-03-01T10:10:00Z",
          error_message: null,
          chain_hash:
            "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
          run_metadata: {},
          created_at: "2026-03-01T10:00:00Z",
        }),
      )
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}/sections`, async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          {
            id: "sec-1",
            run_id: runId,
            section_type: "PROFIT_AND_LOSS",
            section_order: 1,
            title: "Profit and Loss",
            section_hash: "aa11bb22cc33dd44",
            rendered_at: "2026-03-01T10:10:00Z",
          },
          {
            id: "sec-2",
            run_id: runId,
            section_type: "BALANCE_SHEET",
            section_order: 2,
            title: "Balance Sheet",
            section_hash: "ee55ff66aa77bb88",
            rendered_at: "2026-03-01T10:10:01Z",
          },
        ]),
      )
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}/artifacts`, async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          {
            id: "art-1",
            run_id: runId,
            format: "PDF",
            storage_path: "artifacts/board_packs/run-complete-1/report.pdf",
            file_size_bytes: 24576,
            generated_at: "2026-03-01T10:10:05Z",
            checksum: "abc123def456",
          },
          {
            id: "art-2",
            run_id: runId,
            format: "EXCEL",
            storage_path: "artifacts/board_packs/run-complete-1/report.xlsx",
            file_size_bytes: 10240,
            generated_at: "2026-03-01T10:10:06Z",
            checksum: "xyz987uvw654",
          },
        ]),
      )
    })
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([boardPackDefinition]))
    })

    await page.goto(`/board-pack/${runId}`)

    await expect(page.getByRole("button", { name: "Download PDF" })).toBeEnabled()
    await expect(page.getByRole("button", { name: "Download Excel" })).toBeEnabled()
    await expect(page.getByText(/^Chain:/)).toBeVisible()
  })

  test("Report FAILED run disables downloads and shows error", async ({ page }) => {
    const runId = "report-run-failed-1"

    await page.route(`**/api/v1/reports/runs/${runId}`, async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          id: runId,
          tenant_id: "tenant-001",
          definition_id: reportDefinition.id,
          status: "FAILED",
          triggered_by: "user-001",
          started_at: "2026-03-01T10:00:00Z",
          completed_at: "2026-03-01T10:03:00Z",
          error_message: "Engine timeout",
          row_count: null,
          run_metadata: {},
          created_at: "2026-03-01T10:00:00Z",
        }),
      )
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([reportDefinition]))
    })
    await page.route("**/api/v1/reports/metrics", async (route) => {
      await fulfillJson(route, apiResponse([reportMetric]))
    })

    await page.goto(`/reports/${runId}`)

    await expect(page.getByText("Engine timeout")).toBeVisible()
    await expect(page.getByRole("button", { name: /Download CSV/i })).toBeDisabled()
    await expect(page.getByRole("button", { name: /Download Excel/i })).toBeDisabled()
    await expect(page.getByRole("button", { name: /Download PDF/i })).toBeDisabled()
  })

  test("Scheduled delivery trigger shows success state", async ({ page }) => {
    const scheduleId = schedule.id

    await page.route("**/api/v1/delivery/schedules**", async (route) => {
      const request = route.request()
      if (
        request.method() === "POST" &&
        request.url().includes(`/api/v1/delivery/schedules/${scheduleId}/trigger`)
      ) {
        await fulfillJson(
          route,
          apiResponse({ schedule_id: scheduleId, status: "triggered" }),
          202,
        )
        return
      }

      if (request.method() === "GET") {
        await fulfillJson(route, apiResponse([schedule]))
        return
      }

      await route.continue()
    })

    await page.goto("/scheduled-delivery")

    await expect(page.getByRole("cell", { name: schedule.name })).toBeVisible()
    await page.getByRole("button", { name: "Trigger Now" }).first().click()
    await expect(page.getByText("Schedule triggered successfully.")).toBeVisible()
  })

  test("Anomaly snooze dialog requires date", async ({ page }) => {
    await page.route("**/api/v1/anomalies**", async (route) => {
      await fulfillJson(route, apiResponse([anomalyAlert]))
    })

    await page.goto("/anomalies")

    await page.getByRole("button", { name: "Snooze" }).first().click()
    await expect(page.getByRole("heading", { name: "Snooze Alert" })).toBeVisible()

    await page.locator("#snooze-until").fill("")
    await page.getByRole("button", { name: "Save Snooze" }).click()

    await expect(page.getByText("Select a snooze-until date.")).toBeVisible()
  })

  test("Sidebar shows all Phase 5 nav items", async ({ page }) => {
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/board-packs/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/board-pack")

    const sidebar = page.locator("aside").first()

    const boardPacksLink = sidebar.getByRole("link", { name: "Board Packs" })
    const reportsLink = sidebar.getByRole("link", { name: "Reports" })
    const scheduledDeliveryLink = sidebar.getByRole("link", {
      name: "Scheduled Delivery",
    })
    const anomaliesLink = sidebar.getByRole("link", { name: "Anomalies" })

    await expect(boardPacksLink).toBeVisible()
    await expect(reportsLink).toBeVisible()
    await expect(scheduledDeliveryLink).toBeVisible()
    await expect(anomaliesLink).toBeVisible()

    await expect(boardPacksLink).toHaveAttribute("href", "/board-pack")
    await expect(reportsLink).toHaveAttribute("href", "/reports")
    await expect(scheduledDeliveryLink).toHaveAttribute("href", "/scheduled-delivery")
    await expect(anomaliesLink).toHaveAttribute("href", "/anomalies")
  })
})