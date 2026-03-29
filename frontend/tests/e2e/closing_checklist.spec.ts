import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const checklistPayload = (period: string, options?: { overdue?: boolean; autoCompleted?: boolean }) => ({
  run: {
    id: `run-${period}`,
    period,
    status: "open",
    progress_pct: "0.00",
    target_close_date: "2026-03-05",
    actual_close_date: null,
    days_until_period_end: 8,
    is_overdue: false,
    completed_count: 0,
    total_count: 3,
  },
  tasks: [
    {
      id: `task-${period}-1`,
      run_id: `run-${period}`,
      template_task_id: "tmpl-1",
      task_name: "ERP data sync complete",
      assigned_to: null,
      assigned_role: null,
      due_date: options?.overdue ? "2020-01-01" : "2026-03-01",
      status: "not_started",
      completed_at: null,
      completed_by: null,
      notes: null,
      is_auto_completed: Boolean(options?.autoCompleted),
      auto_completed_by_event: options?.autoCompleted ? "erp_sync_complete" : null,
      order_index: 1,
      dependency_met: true,
      depends_on_task_ids: [],
    },
    {
      id: `task-${period}-2`,
      run_id: `run-${period}`,
      template_task_id: "tmpl-2",
      task_name: "GL/TB reconciliation",
      assigned_to: null,
      assigned_role: null,
      due_date: "2026-03-02",
      status: "not_started",
      completed_at: null,
      completed_by: null,
      notes: null,
      is_auto_completed: false,
      auto_completed_by_event: null,
      order_index: 2,
      dependency_met: true,
      depends_on_task_ids: [],
    },
    {
      id: `task-${period}-3`,
      run_id: `run-${period}`,
      template_task_id: "tmpl-3",
      task_name: "MIS review and approval",
      assigned_to: null,
      assigned_role: "finance_leader",
      due_date: "2026-03-03",
      status: "not_started",
      completed_at: null,
      completed_by: null,
      notes: null,
      is_auto_completed: false,
      auto_completed_by_event: null,
      order_index: 3,
      dependency_met: true,
      depends_on_task_ids: ["tmpl-2"],
    },
  ],
})

test.describe("Closing checklist", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)

    await page.route("**/api/v1/close/analytics", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          avg_days_to_close: "5.20",
          fastest_close_period: "2026-01",
          slowest_close_period: "2025-12",
          on_time_rate: "87.00",
          most_blocked_task: "MIS review and approval",
          trend: "improving",
        }),
      )
    })
  })

  test("checklist page loads", async ({ page }) => {
    await page.route("**/api/v1/close/*", async (route) => {
      const period = route.request().url().split("/").pop() ?? "2026-03"
      await fulfillJson(route, apiResponse(checklistPayload(period)))
    })

    await page.goto("/close")
    await expect(page.getByTestId("progress-ring")).toBeVisible()
    await expect(page.getByTestId("checklist-task-card").first()).toBeVisible()
  })

  test("task status update", async ({ page }) => {
    await page.route("**/api/v1/close/2026-03", async (route) => {
      await fulfillJson(route, apiResponse(checklistPayload("2026-03")))
    })

    await page.route("**/api/v1/close/2026-03/tasks/*", async (route) => {
      await fulfillJson(
        route,
        apiResponse({
          task: {
            id: "task-2026-03-1",
            status: "in_progress",
            notes: "Working now",
            completed_at: null,
          },
          run: { id: "run-2026-03", status: "in_progress", progress_pct: "33.33" },
        }),
      )
    })

    await page.goto("/close/2026-03")
    await page.getByRole("button", { name: "Open" }).first().click()
    await page.getByLabel("Status").selectOption("in_progress")
    await page.getByRole("button", { name: "Save Changes" }).click()

    await expect(page.getByText("in_progress").first()).toBeVisible()
    await expect(page.getByText("1 / 3")).toBeVisible()
  })

  test("overdue task shows red", async ({ page }) => {
    await page.route("**/api/v1/close/2026-03", async (route) => {
      await fulfillJson(route, apiResponse(checklistPayload("2026-03", { overdue: true })))
    })

    await page.goto("/close/2026-03")
    await expect(page.getByTestId("overdue-indicator").first()).toBeVisible()
  })

  test("period selector works", async ({ page }) => {
    await page.route("**/api/v1/close/2026-03", async (route) => {
      await fulfillJson(route, apiResponse(checklistPayload("2026-03")))
    })
    await page.route("**/api/v1/close/2026-02", async (route) => {
      await fulfillJson(route, apiResponse(checklistPayload("2026-02")))
    })

    await page.goto("/close/2026-03")
    await page.getByLabel("Period").selectOption("2026-02")
    await expect(page).toHaveURL(/\/close\/2026-02/)
  })

  test("autocompleted task shows badge", async ({ page }) => {
    await page.route("**/api/v1/close/2026-03", async (route) => {
      await fulfillJson(route, apiResponse(checklistPayload("2026-03", { autoCompleted: true })))
    })

    await page.goto("/close/2026-03")
    await expect(page.getByTestId("autocompleted-badge").first()).toBeVisible()
  })
})
