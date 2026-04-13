import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const metricRevenue = {
  key: "mis.kpi.revenue",
  label: "Revenue",
  source_table: "metric_results",
  source_column: "revenue",
  data_type: "decimal",
  engine: "mis",
}

const metricEbitda = {
  key: "mis.kpi.ebitda",
  label: "EBITDA",
  source_table: "metric_results",
  source_column: "ebitda",
  data_type: "decimal",
  engine: "mis",
}

const metricCashFlow = {
  key: "cashflow.operating_cf",
  label: "Operating Cash Flow",
  source_table: "cash_flow_line_results",
  source_column: "operating_cf",
  data_type: "decimal",
  engine: "cash_flow",
}

const definition = {
  id: "report-def-1",
  tenant_id: "tenant-001",
  name: "Monthly Report",
  description: "Custom report",
  metric_keys: [metricRevenue.key, metricEbitda.key],
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
  sort_config: { field: metricRevenue.key, direction: "ASC" },
  export_formats: ["CSV", "EXCEL", "PDF"],
  config: {},
  created_by: "user-001",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  is_active: true,
}

const runComplete = {
  id: "report-run-1",
  tenant_id: "tenant-001",
  definition_id: definition.id,
  status: "COMPLETE",
  triggered_by: "user-001",
  started_at: "2026-03-01T10:00:00Z",
  completed_at: "2026-03-01T10:03:00Z",
  error_message: null,
  row_count: 3,
  run_metadata: {},
  created_at: "2026-03-01T10:00:00Z",
}

const runPending = {
  ...runComplete,
  id: "report-run-pending-1",
  status: "PENDING",
  completed_at: null,
  row_count: null,
}

test.describe("Reports pages", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Reports list page loads", async ({ page }) => {
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/reports/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/reports")

    await expect(
      page.locator("main").getByRole("heading", { name: "Custom Reports" }),
    ).toBeVisible()
    await expect(page.getByRole("button", { name: "Runs" })).toBeVisible()
    await expect(page.getByRole("button", { name: "New Report" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Runs" })).toHaveClass(
      /brand-primary/,
    )
  })

  test("Create report sheet opens and validates metric selection", async ({
    page,
  }) => {
    await page.route("**/api/v1/reports/metrics", async (route) => {
      await fulfillJson(
        route,
        apiResponse([metricRevenue, metricEbitda, metricCashFlow]),
      )
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/reports/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/reports")
    await page.getByRole("button", { name: "New Report" }).click()

    await expect(page.getByRole("heading", { name: "Create Report" })).toBeVisible()
    await expect(page.locator("#report-name")).toBeVisible()
    await page.locator("#report-name").fill("Test Report")
    await page.getByRole("button", { name: "Next" }).click()

    await expect(page.locator("summary").filter({ hasText: /^mis$/ })).toBeVisible()
    await expect(
      page.locator("summary").filter({ hasText: /^cash_flow$/ }),
    ).toBeVisible()

    await page.getByRole("button", { name: "Next" }).click()
    await expect(page.getByText("Select at least one metric.")).toBeVisible()
  })

  test("Full report definition creation flow", async ({ page }) => {
    let created = false

    await page.route("**/api/v1/reports/metrics", async (route) => {
      await fulfillJson(route, apiResponse([metricRevenue, metricEbitda]))
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse(created ? [definition] : []))
    })
    await page.route("**/api/v1/reports/runs?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/reports/definitions", async (route) => {
      created = true
      await fulfillJson(route, apiResponse(definition), 201)
    })

    await page.goto("/reports")
    await page.getByRole("button", { name: "New Report" }).click()

    await page.locator("#report-name").fill("Test Report")
    await page.getByRole("button", { name: "Next" }).click()

    await page.getByRole("checkbox", { name: "Revenue (mis.kpi.revenue)" }).check()
    await page.getByRole("button", { name: "Next" }).click()

    await page.locator("#period-start").fill("2024-03-01")
    await page.locator("#period-end").fill("2024-03-31")
    await page.getByRole("button", { name: "Next" }).click()
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByRole("heading", { name: "Create Report" })).not.toBeVisible()
    await expect(page.getByRole("button", { name: "Definitions" })).toHaveClass(
      /brand-primary/,
    )
  })

  test("Run viewer shows result table and download buttons", async ({ page }) => {
    const runId = runComplete.id
    await page.route(`**/api/v1/reports/runs/${runId}`, async (route) => {
      await fulfillJson(route, apiResponse(runComplete))
    })
    await page.route(`**/api/v1/reports/runs/${runId}/result`, async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          id: "result-1",
          run_id: runId,
          result_data: [
            { [metricRevenue.key]: "1000.00", [metricEbitda.key]: "200.00" },
            { [metricRevenue.key]: "1500.00", [metricEbitda.key]: "250.00" },
            { [metricRevenue.key]: "1800.00", [metricEbitda.key]: "300.00" },
          ],
          result_hash:
            "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
          export_path_csv: "/tmp/r1.csv",
          export_path_excel: "/tmp/r1.xlsx",
          export_path_pdf: "/tmp/r1.pdf",
          created_at: "2026-03-01T10:03:00Z",
        }),
      )
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route("**/api/v1/reports/metrics", async (route) => {
      await fulfillJson(route, apiResponse([metricRevenue, metricEbitda]))
    })

    await page.goto(`/reports/${runId}`)

    await expect(page.getByText(/Rows:\s*3/)).toBeVisible()
    await expect(page.getByRole("button", { name: /Download CSV/i })).toBeEnabled()
    await expect(page.getByRole("button", { name: /Download Excel/i })).toBeEnabled()
    await expect(page.getByRole("button", { name: /Download PDF/i })).toBeEnabled()
    await expect(page.getByRole("columnheader", { name: "Revenue" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "EBITDA" })).toBeVisible()
    await expect(page.getByText(/^Result hash:/)).toBeVisible()
  })

  test("Failed run shows error message, downloads disabled", async ({ page }) => {
    const runId = "report-run-failed-1"
    await page.route(`**/api/v1/reports/runs/${runId}`, async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          ...runPending,
          id: runId,
          status: "FAILED",
          error_message: "Query timeout exceeded",
        }),
      )
    })
    await page.route("**/api/v1/reports/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route("**/api/v1/reports/metrics", async (route) => {
      await fulfillJson(route, apiResponse([metricRevenue, metricEbitda]))
    })

    await page.goto(`/reports/${runId}`)

    await expect(page.getByText("Query timeout exceeded")).toBeVisible()
    await expect(page.getByRole("button", { name: /Download CSV/i })).toBeDisabled()
    await expect(page.getByRole("button", { name: /Download Excel/i })).toBeDisabled()
    await expect(page.getByRole("button", { name: /Download PDF/i })).toBeDisabled()
  })
})
