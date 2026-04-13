import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"
import { dispatchComponentHookState } from "./helpers/react-state"

const definition = {
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

const pendingRun = {
  id: "run-pending-1",
  tenant_id: "tenant-001",
  definition_id: "def-1",
  period_start: "2024-03-01",
  period_end: "2024-03-31",
  status: "PENDING",
  triggered_by: "user-001",
  started_at: null,
  completed_at: null,
  error_message: null,
  chain_hash: null,
  run_metadata: {},
  created_at: "2026-03-01T10:00:00Z",
}

const completeRun = {
  ...pendingRun,
  id: "run-complete-1",
  status: "COMPLETE",
  chain_hash: "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  completed_at: "2026-03-01T10:10:00Z",
}

test.describe("Board pack pages", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Board pack list page loads", async ({ page }) => {
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route("**/api/v1/board-packs/runs**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/board-pack")

    await expect(
      page.locator("main").getByRole("heading", { name: "Board Packs" }),
    ).toBeVisible()
    await expect(page.getByRole("button", { name: "Runs" })).toBeVisible()
    await expect(page.getByRole("button", { name: "New Pack" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Runs" })).toHaveClass(/brand-primary/)
  })

  test("Generate modal opens and validates period", async ({ page }) => {
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route("**/api/v1/board-packs/runs**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/board-pack")
    await page.getByRole("button", { name: "New Pack" }).click()

    await expect(page.getByRole("heading", { name: "Generate Board Pack" })).toBeVisible()
    await expect(page.locator("#generate-definition")).toBeVisible()
    await expect(page.locator("#generate-period-start")).toBeVisible()
    await expect(page.locator("#generate-period-end")).toBeVisible()

    await dispatchComponentHookState(page, "BoardPackPage", "New Pack", [
      { index: 13, value: [definition] },
      { index: 14, value: false },
      { index: 15, value: null },
      { index: 23, value: [] },
      { index: 24, value: false },
      { index: 25, value: null },
    ])
    await page.locator("#generate-definition").selectOption("def-1")
    await page.locator("#generate-period-start").fill("2024-03-01")
    await page.locator("#generate-period-end").fill("2024-01-01")
    await page.locator("div.fixed.inset-0").getByRole("button", { name: "Generate" }).click()

    await expect(page.getByText("Period End must be on or after Period Start.")).toBeVisible()
  })

  test("Generate success creates run and switches to Runs tab", async ({ page }) => {
    let hasGenerated = false
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route("**/api/v1/board-packs/runs**", async (route) => {
      const payload = hasGenerated ? [pendingRun] : []
      await fulfillJson(route, apiResponse(payload))
    })
    await page.route("**/api/v1/board-packs/generate", async (route) => {
      hasGenerated = true
      await fulfillJson(route, apiResponse(pendingRun), 202)
    })

    await page.goto("/board-pack")
    await page.getByRole("button", { name: "Definitions" }).click()
    await page.getByRole("button", { name: "New Pack" }).click()

    await dispatchComponentHookState(page, "BoardPackPage", "New Pack", [
      { index: 13, value: [definition] },
      { index: 14, value: false },
      { index: 15, value: null },
      { index: 23, value: [] },
      { index: 24, value: false },
      { index: 25, value: null },
    ])
    await page.locator("#generate-definition").selectOption("def-1")
    await page.locator("#generate-period-start").fill("2024-03-01")
    await page.locator("#generate-period-end").fill("2024-03-31")
    await page.locator("div.fixed.inset-0").getByRole("button", { name: "Generate" }).click()

    await dispatchComponentHookState(page, "BoardPackPage", "New Pack", [
      { index: 23, value: [pendingRun] },
      { index: 24, value: false },
      { index: 25, value: null },
    ])
    await expect(page.getByRole("heading", { name: "Generate Board Pack" })).not.toBeVisible()
    await expect(page.getByRole("button", { name: "Runs" })).toHaveClass(/brand-primary/)
    await expect(page.getByText("PENDING")).toBeVisible()
  })

  test("Run viewer shows sections and download buttons", async ({ page }) => {
    const runId = "run-complete-1"
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}`, async (route) => {
      await fulfillJson(route, apiResponse({ ...completeRun, id: runId }))
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

    await page.goto(`/board-pack/${runId}`)

    await expect(page.getByText(/^Chain:/)).toBeVisible()
    await expect(page.getByRole("button", { name: "Download PDF" })).toBeEnabled()
    await expect(page.getByRole("button", { name: "Download Excel" })).toBeEnabled()
    await expect(page.locator("details")).toHaveCount(2)
  })

  test("Failed run shows error message", async ({ page }) => {
    const runId = "run-failed-1"
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([definition]))
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}`, async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          ...pendingRun,
          id: runId,
          status: "FAILED",
          error_message: "Source data unavailable",
        }),
      )
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}/sections`, async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route(`**/api/v1/board-packs/runs/${runId}/artifacts`, async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto(`/board-pack/${runId}`)

    await expect(page.getByText("Source data unavailable")).toBeVisible()
    await expect(page.getByRole("button", { name: "Download PDF" })).toBeDisabled()
    await expect(page.getByRole("button", { name: "Download Excel" })).toBeDisabled()
  })
})
