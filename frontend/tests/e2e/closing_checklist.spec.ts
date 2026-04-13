import { expect, test, type Page } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

type MonthendChecklistSummary = {
  checklist_id: string
  period_year: number
  period_month: number
  entity_name: string
  status: string
  created_at: string
}

type MonthendChecklistTask = {
  task_id: string
  task_name: string
  task_category: string
  priority: string
  status: string
  assigned_to: string | null
  sort_order: number
  is_required: boolean
  completed_at: string | null
}

type MonthendChecklistDetail = MonthendChecklistSummary & {
  closed_at: string | null
  tasks: MonthendChecklistTask[]
}

function makeSummary(period: string, overrides: Partial<MonthendChecklistSummary> = {}): MonthendChecklistSummary {
  const [year, month] = period.split("-").map(Number)
  return {
    checklist_id: `checklist-${period}`,
    period_year: year,
    period_month: month,
    entity_name: "Acme Ltd",
    status: "OPEN",
    created_at: `${period}-05T09:00:00Z`,
    ...overrides,
  }
}

function makeDetail(
  period: string,
  overrides: Partial<MonthendChecklistDetail> = {},
): MonthendChecklistDetail {
  return {
    ...makeSummary(period),
    closed_at: null,
    tasks: [
      {
        task_id: `task-${period}-1`,
        task_name: "ERP data sync complete",
        task_category: "Data",
        priority: "High",
        status: "open",
        assigned_to: null,
        sort_order: 1,
        is_required: true,
        completed_at: null,
      },
      {
        task_id: `task-${period}-2`,
        task_name: "GL/TB reconciliation",
        task_category: "Accounting",
        priority: "Medium",
        status: "open",
        assigned_to: null,
        sort_order: 2,
        is_required: true,
        completed_at: null,
      },
      {
        task_id: `task-${period}-3`,
        task_name: "MIS review and approval",
        task_category: "Review",
        priority: "Low",
        status: "open",
        assigned_to: "user-001",
        sort_order: 3,
        is_required: true,
        completed_at: null,
      },
    ],
    ...overrides,
  }
}

async function mockCloseChecklistPage(
  page: Page,
  options?: {
    detailsByPeriod?: Record<string, MonthendChecklistDetail>
    readiness?: {
      pass: boolean
      blockers: string[]
      warnings: string[]
    }
  },
): Promise<void> {
  const detailsByPeriod = options?.detailsByPeriod ?? {
    "2026-03": makeDetail("2026-03"),
  }
  const summaries = Object.values(detailsByPeriod).map((detail) =>
    makeSummary(`${detail.period_year}-${String(detail.period_month).padStart(2, "0")}`, {
      checklist_id: detail.checklist_id,
      entity_name: detail.entity_name,
      status: detail.status,
      created_at: detail.created_at,
    }),
  )

  await page.route("**/api/v1/monthend**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/\/+$/, "")

    if (path === "/api/v1/monthend") {
      await fulfillJson(
        route,
        apiResponse({
          checklists: summaries,
          count: summaries.length,
        }),
      )
      return
    }

    if (path.includes("/tasks/")) {
      const parts = path.split("/")
      const taskId = parts.at(-1) ?? ""
      const checklistId = parts.at(-3) ?? ""
      const target = Object.values(detailsByPeriod).find((detail) => detail.checklist_id === checklistId)
      if (!target) {
        await fulfillJson(route, apiResponse({ ok: false }), 404)
        return
      }
      target.tasks = target.tasks.map((task) =>
        task.task_id === taskId
          ? {
              ...task,
              status: "completed",
              completed_at: "2026-03-31T18:00:00Z",
            }
          : task,
      )
      await fulfillJson(route, apiResponse({ ok: true }))
      return
    }

    if (path.endsWith("/close")) {
      await fulfillJson(route, apiResponse({ ok: true }))
      return
    }

    const checklistId = path.split("/").pop() ?? ""
    const target = Object.values(detailsByPeriod).find((detail) => detail.checklist_id === checklistId)
    if (!target) {
      await fulfillJson(route, apiResponse({ ok: false }), 404)
      return
    }
    await fulfillJson(route, apiResponse(target))
  })

  await page.route("**/api/v1/close/run-readiness", async (route) => {
    await fulfillJson(
      route,
      apiResponse({
        pass: options?.readiness?.pass ?? false,
        blockers: options?.readiness?.blockers ?? ["Unposted journals remain for the selected period."],
        warnings: options?.readiness?.warnings ?? ["FX revaluation is not yet confirmed."],
        metrics: {
          pending_journals: 2,
          trial_balance_total_debit: "1000.00",
          trial_balance_total_credit: "1000.00",
          fx_entities_exist: true,
          revaluation_done: false,
          translation_done: false,
          group_exists: true,
          consolidation_done: false,
          coa_present: true,
        },
      }),
    )
  })
}

test.describe("Closing checklist", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("checklist page loads", async ({ page }) => {
    await mockCloseChecklistPage(page)

    await page.goto("/close/checklist?period=2026-03")

    await expect(page.getByRole("heading", { name: "Close Checklist" })).toBeVisible()
    await expect(page.getByText("Acme Ltd 2026-03")).toBeVisible()
    await expect(page.getByRole("cell", { name: "ERP data sync complete" })).toBeVisible()
    await expect(page.getByText("0 of 3 tasks complete")).toBeVisible()
  })

  test("task status update", async ({ page }) => {
    await mockCloseChecklistPage(page)

    await page.goto("/close/checklist?period=2026-03")
    await page.getByRole("button", { name: "Mark Complete" }).first().evaluate((button) => {
      ;(button as HTMLButtonElement).click()
    })

    await expect(page.getByText("1 of 3 tasks complete")).toBeVisible()
    await expect(page.getByRole("cell", { name: "2026-03-31T18:00:00Z" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Mark Complete" }).first()).toBeDisabled()
  })

  test("readiness blockers are shown when the checklist is not ready", async ({ page }) => {
    await mockCloseChecklistPage(page, {
      readiness: {
        pass: false,
        blockers: ["Cash application is still pending."],
        warnings: ["Translation run is not complete."],
      },
    })

    await page.goto("/close/checklist?period=2026-03")

    await expect(page.getByText("Status:")).toBeVisible()
    await expect(page.getByText("FAIL")).toBeVisible()
    await expect(page.getByText("Cash application is still pending.")).toBeVisible()
    await expect(page.getByText("Translation run is not complete.")).toBeVisible()
  })

  test("period selector works", async ({ page }) => {
    await mockCloseChecklistPage(page, {
      detailsByPeriod: {
        "2026-03": makeDetail("2026-03"),
        "2026-02": makeDetail("2026-02", {
          tasks: [
            {
              task_id: "task-2026-02-1",
              task_name: "February close sign-off",
              task_category: "Review",
              priority: "High",
              status: "completed",
              assigned_to: "user-001",
              sort_order: 1,
              is_required: true,
              completed_at: "2026-02-29T17:00:00Z",
            },
          ],
        }),
      },
    })

    await page.goto("/close/checklist?period=2026-03")
    await page.locator('input[type="month"]').evaluate((input) => {
      const element = input as HTMLInputElement
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
      descriptor?.set?.call(element, "2026-02")
      element.dispatchEvent(new Event("input", { bubbles: true }))
      element.dispatchEvent(new Event("change", { bubbles: true }))
    })

    await expect(page.getByText("Acme Ltd 2026-02")).toBeVisible()
    await expect(page.getByRole("cell", { name: "February close sign-off" })).toBeVisible()
  })

  test("completed task shows the current status badge", async ({ page }) => {
    await mockCloseChecklistPage(page, {
      detailsByPeriod: {
        "2026-03": makeDetail("2026-03", {
          tasks: [
            {
              task_id: "task-2026-03-1",
              task_name: "ERP data sync complete",
              task_category: "Data",
              priority: "High",
              status: "completed",
              assigned_to: null,
              sort_order: 1,
              is_required: true,
              completed_at: "2026-03-31T18:00:00Z",
            },
            {
              task_id: "task-2026-03-2",
              task_name: "GL/TB reconciliation",
              task_category: "Accounting",
              priority: "Medium",
              status: "open",
              assigned_to: null,
              sort_order: 2,
              is_required: true,
              completed_at: null,
            },
          ],
        }),
      },
    })

    await page.goto("/close/checklist?period=2026-03")

    const completedRow = page.getByRole("row", { name: /ERP data sync complete/i })
    await expect(completedRow.getByText("completed")).toBeVisible()
    await expect(completedRow.getByRole("button", { name: "Mark Complete" })).toBeDisabled()
    await expect(page.getByText("1 of 2 tasks complete")).toBeVisible()
  })
})
