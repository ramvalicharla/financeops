import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const connections = [
  {
    id: "conn-1",
    tenant_id: "tenant-001",
    connector_type: "ZOHO",
    display_name: "Connection 1",
    last_sync_at: "2026-03-01T12:00:00Z",
    last_sync_status: "COMPLETED",
    is_active: true,
    created_at: "2026-03-01T10:00:00Z",
  },
]

const syncRuns = [
  {
    id: "run-1",
    connection_id: "conn-1",
    dataset_type: "GENERAL_LEDGER",
    status: "COMPLETED",
    started_at: "2026-03-01T12:00:00Z",
    completed_at: "2026-03-01T12:05:00Z",
    duration_seconds: 300,
    records_extracted: 120,
    drift_severity: "NONE",
    publish_event_id: "pub-1",
    validation_results: [],
    error_message: null,
  },
]

test.describe("Reconciliation pages", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse(connections))
    })
    await page.route("**/api/v1/erp-sync/sync-runs**", async (route) => {
      await fulfillJson(route, apiResponse(syncRuns))
    })
  })

  test("GL/TB page loads", async ({ page }) => {
    await page.route("**/api/v1/reconciliation/gl-tb?**", async (route) => {
      await fulfillJson(route, apiResponse({
        run_id: "run-1",
        entity_id: "entity-001",
        period: "2026-03",
        total_accounts: 0,
        matched_accounts: 0,
        variance_accounts: 0,
        total_variance: "0",
        accounts: [],
        generated_at: "2026-03-01T12:00:00Z",
      }))
    })

    await page.goto("/reconciliation/gl-tb")
    await expect(page.getByLabel("Entity")).toBeVisible()
    await expect(page.getByLabel("Period")).toBeVisible()
    await expect(page.getByLabel("Sync Run")).toBeVisible()
  })

  test("GL/TB results load after filter selection", async ({ page }) => {
    await page.route("**/api/v1/reconciliation/gl-tb?**", async (route) => {
      const accounts = Array.from({ length: 10 }).map((_, index) => ({
        account_code: `AC-${index + 1}`,
        account_name: `Account ${index + 1}`,
        account_type: "EXPENSE",
        tb_balance: "1000.00",
        gl_balance: "1000.00",
        variance: "0.00",
        variance_pct: "0.00",
        status: "MATCHED",
        journal_entries: [],
      }))
      await fulfillJson(route, apiResponse({
        run_id: "run-1",
        entity_id: "entity-001",
        period: "2026-03",
        total_accounts: 10,
        matched_accounts: 10,
        variance_accounts: 0,
        total_variance: "0.00",
        accounts,
        generated_at: "2026-03-01T12:00:00Z",
      }))
    })

    await page.goto("/reconciliation/gl-tb")
    await page.getByLabel("Entity").selectOption("entity-001")
    await page.getByLabel("Sync Run").selectOption("run-1")
    await expect(page.getByText("Total Accounts")).toBeVisible()
    await expect(page.locator("table").first().locator("tbody tr")).toHaveCount(10)
  })

  test("Variance row drill-down", async ({ page }) => {
    await page.route("**/api/v1/reconciliation/gl-tb?**", async (route) => {
      await fulfillJson(route, apiResponse({
        run_id: "run-1",
        entity_id: "entity-001",
        period: "2026-03",
        total_accounts: 1,
        matched_accounts: 0,
        variance_accounts: 1,
        total_variance: "100.00",
        accounts: [
          {
            account_code: "AC-1",
            account_name: "Payroll Expense",
            account_type: "EXPENSE",
            tb_balance: "1000.00",
            gl_balance: "900.00",
            variance: "100.00",
            variance_pct: "10.00",
            status: "VARIANCE",
            journal_entries: [
              {
                entry_id: "je-1",
                date: "2026-03-01",
                description: "Payroll posting",
                debit: "900.00",
                credit: "0.00",
                reference: "JV-1",
              },
            ],
          },
        ],
        generated_at: "2026-03-01T12:00:00Z",
      }))
    })

    await page.goto("/reconciliation/gl-tb")
    await page.getByLabel("Entity").selectOption("entity-001")
    await page.getByLabel("Sync Run").selectOption("run-1")
    await page.getByRole("cell", { name: "Payroll Expense" }).click()
    await expect(page.getByText("Payroll Expense")).toBeVisible()
    await expect(page.getByText("Payroll posting")).toBeVisible()
  })

  test("Payroll recon loads", async ({ page }) => {
    await page.route("**/api/v1/reconciliation/payroll?**", async (route) => {
      await fulfillJson(route, apiResponse({
        run_id: "run-1",
        entity_id: "entity-001",
        period: "2026-03",
        payroll_gross: "10000.00",
        gl_gross: "10000.00",
        gross_variance: "0.00",
        payroll_net: "8000.00",
        gl_net: "7900.00",
        net_variance: "100.00",
        payroll_deductions: "2000.00",
        gl_deductions: "2100.00",
        deductions_variance: "-100.00",
        cost_centres: [
          {
            cost_centre_id: "cc-1",
            cost_centre_name: "Sales",
            payroll_amount: "4000.00",
            gl_amount: "3900.00",
            variance: "100.00",
            status: "VARIANCE",
            employees: [],
          },
        ],
      }))
    })

    await page.goto("/reconciliation/payroll")
    await page.getByLabel("Entity").selectOption("entity-001")
    await page.getByLabel("Sync Run").selectOption("run-1")
    await expect(page.getByText("Payroll Gross")).toBeVisible()
    await expect(page.getByText("Cost Centres")).toBeVisible()
  })

  test("Error state", async ({ page }) => {
    await page.route("**/api/v1/reconciliation/gl-tb?**", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "failed" },
          meta: { request_id: "req-err", timestamp: new Date().toISOString() },
        },
        500,
      )
    })
    await page.goto("/reconciliation/gl-tb")
    await page.getByLabel("Entity").selectOption("entity-001")
    await page.getByLabel("Sync Run").selectOption("run-1")
    await expect(page.getByText("Failed to load GL/TB reconciliation results.")).toBeVisible()
    await expectNotCrashed(page)
  })
})
