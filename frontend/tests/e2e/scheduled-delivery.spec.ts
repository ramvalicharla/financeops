import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

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

test.describe("Scheduled delivery pages", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Page loads and New Schedule button is visible", async ({ page }) => {
    await page.route("**/api/v1/delivery/schedules**", async (route) => {
      await fulfillJson(route, apiResponse([schedule]))
    })
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/scheduled-delivery")

    await expect(
      page.locator("main").getByRole("heading", { name: "Scheduled Delivery" }),
    ).toBeVisible()
    await expect(page.getByRole("button", { name: "New Schedule" })).toBeVisible()
  })

  test("Create schedule sheet validates empty recipients", async ({ page }) => {
    await page.route("**/api/v1/delivery/schedules**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([{ id: "def-1", name: "Monthly Board Pack" }]))
    })

    await page.goto("/scheduled-delivery")
    await page.getByRole("button", { name: "New Schedule" }).click()

    await expect(page.getByRole("heading", { name: "Create Schedule" })).toBeVisible()
    await page.locator("#delivery-name").fill("My Schedule")
    await page.locator("#delivery-source").selectOption("def-1")
    await page.locator("#delivery-cron").fill("0 8 * * 1")
    await page.getByRole("button", { name: "Remove" }).click()
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("At least one recipient is required.")).toBeVisible()
  })

  test("Trigger Now posts trigger endpoint and shows success state", async ({ page }) => {
    await page.route("**/delivery/schedules**", async (route) => {
      const requestUrl = route.request().url()
      if (
        route.request().method() === "POST" &&
        requestUrl.includes("/delivery/schedules/") &&
        requestUrl.includes("/trigger")
      ) {
        await fulfillJson(
          route,
          apiResponse({ schedule_id: "sched-1", status: "triggered" }),
          202,
        )
        return
      }
      if (route.request().method() === "GET") {
        await fulfillJson(route, apiResponse([schedule]))
        return
      }
      await route.continue()
    })
    await page.route("**/api/v1/board-packs/definitions?**", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/scheduled-delivery")
    const triggerRequest = page.waitForRequest((request) => {
      return (
        request.method() === "POST" &&
        request.url().includes("/delivery/schedules/") &&
        request.url().includes("/trigger")
      )
    })
    await page.getByRole("button", { name: "Trigger Now" }).click()
    await triggerRequest

    await expect(page.getByText("Schedule triggered successfully.")).toBeVisible()
  })
})
