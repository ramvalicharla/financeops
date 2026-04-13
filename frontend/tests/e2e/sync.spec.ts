import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const buildConnection = (index: number) => ({
  id: `conn-${index}`,
  tenant_id: "tenant-001",
  connector_type: "ZOHO",
  display_name: `Connection ${index}`,
  last_sync_at: "2026-03-01T12:00:00Z",
  last_sync_status: "COMPLETED",
  is_active: true,
  created_at: "2026-03-01T10:00:00Z",
})

const buildRun = (index: number, status: string) => ({
  id: `run-${index}`,
  connection_id: "conn-1",
  dataset_type: "GENERAL_LEDGER",
  status,
  started_at: "2026-03-01T12:00:00Z",
  completed_at: "2026-03-01T12:05:00Z",
  duration_seconds: 300,
  records_extracted: 120,
  drift_severity: "NONE",
  publish_event_id: null,
  validation_results: [
    { category: "REQUIRED_FIELD_PRESENCE", passed: true, message: null },
    { category: "DUPLICATE_SYNC", passed: true, message: null },
  ],
  error_message: null,
})

test.describe("Sync page", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Sync page loads with connections", async ({ page }) => {
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse([buildConnection(1), buildConnection(2)]))
    })
    await page.route("**/api/v1/erp-sync/sync-runs**", async (route) => {
      await fulfillJson(route, apiResponse([buildRun(1, "COMPLETED")]))
    })

    await page.goto("/sync")

    await expect(page.getByText("Connected Sources")).toBeVisible()
    await expect(page.getByText("Connection 1")).toBeVisible()
    await expect(page.getByText("Connection 2")).toBeVisible()
  })

  test("View sync run history", async ({ page }) => {
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse([buildConnection(1), buildConnection(2)]))
    })
    await page.route("**/api/v1/erp-sync/sync-runs**", async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          buildRun(1, "COMPLETED"),
          buildRun(2, "RUNNING"),
          buildRun(3, "HALTED"),
        ]),
      )
    })

    await page.goto("/sync")
    await page.getByRole("button", { name: "Connection 1" }).click()

    const historyTable = page.locator("table").first()
    await expect(historyTable.locator("tbody tr")).toHaveCount(3)
    await expect(page.getByText("RUNNING")).toBeVisible()
    await expect(page.getByText("HALTED")).toBeVisible()
  })

  test("Trigger sync", async ({ page }) => {
    const runs = [buildRun(1, "COMPLETED")]
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse([buildConnection(1)]))
    })
    await page.route("**/api/v1/erp-sync/bootstrap/test-ready", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          connection_id: "conn-1",
          sync_definition_id: "sync-def-1",
          sync_definition_version_id: "sync-def-ver-1",
        }),
      )
    })
    await page.route("**/api/v1/erp-sync/sync-runs?**", async (route) => {
      await fulfillJson(route, apiResponse(runs))
    })
    await page.route("**/api/v1/erp-sync/sync-runs", async (route) => {
      const runningRun = {
        ...buildRun(99, "RUNNING"),
        id: "run-99",
        status: "RUNNING",
      }
      runs.unshift(runningRun)
      await fulfillJson(route, apiResponse(runningRun))
    })

    await page.goto("/sync")
    await page.getByRole("button", { name: "Sync Now" }).click()
    await expect(page.getByText("RUNNING")).toBeVisible()
  })

  test("View validation report", async ({ page }) => {
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse([buildConnection(1)]))
    })
    await page.route("**/api/v1/erp-sync/sync-runs**", async (route) => {
      await fulfillJson(
        route,
        apiResponse([
          {
            ...buildRun(1, "COMPLETED"),
            validation_results: [
              { category: "REQUIRED_FIELD_PRESENCE", passed: true, message: null },
              { category: "BACKDATED_MODIFICATION", passed: false, message: "Detected" },
            ],
          },
        ]),
      )
    })

    await page.goto("/sync")
    await page.getByRole("button", { name: "Validation Report" }).click()
    await expect(page.getByText("Validation Report")).toBeVisible()
    await expect(page.getByText("REQUIRED_FIELD_PRESENCE")).toBeVisible()
    await expect(page.getByText("BACKDATED_MODIFICATION")).toBeVisible()
  })

  test("Navigate to connect source", async ({ page }) => {
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(route, apiResponse([buildConnection(1)]))
    })
    await page.route("**/api/v1/erp-sync/sync-runs**", async (route) => {
      await fulfillJson(route, apiResponse([buildRun(1, "COMPLETED")]))
    })

    await page.goto("/sync")
    await page.getByRole("button", { name: "Add Source" }).click()
    await expect(page).toHaveURL(/\/sync\/connect$/)
    await expect(page.locator("main").getByRole("heading", { name: "Connect Source" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Connection details" })).toBeVisible()
    await expect(page.getByText("Live ERP authorization is available for Zoho Books and QuickBooks in this flow.")).toBeVisible()
  })

  test("Error state", async ({ page }) => {
    await page.route("**/api/v1/erp-sync/connections", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "boom" },
          meta: { request_id: "req-1", timestamp: new Date().toISOString() },
        },
        500,
      )
    })

    await page.goto("/sync")
    await expect(page.getByText("Server error, please try again")).toBeVisible()
    await expectNotCrashed(page)
  })
})
