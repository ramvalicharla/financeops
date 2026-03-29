import { expect, test, type Page } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

type OnboardingStatePayload = {
  id: string
  tenant_id: string
  current_step: number
  industry: string | null
  template_applied: boolean
  template_applied_at: string | null
  template_id: string | null
  erp_connected: boolean
  completed: boolean
  completed_at: string | null
  created_at: string
  updated_at: string
}

const baseState = (): OnboardingStatePayload => ({
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "tenant-001",
  current_step: 1,
  industry: null,
  template_applied: false,
  template_applied_at: null,
  template_id: null,
  erp_connected: false,
  completed: false,
  completed_at: null,
  created_at: "2026-03-21T10:00:00Z",
  updated_at: "2026-03-21T10:00:00Z",
})

const templateDetail = {
  id: "saas",
  name: "SaaS / Subscription",
  industry: "saas",
  description: "Template preview",
  board_pack_sections: [
    { section_type: "PROFIT_AND_LOSS", title: "P&L" },
    { section_type: "CASH_FLOW", title: "Cash Flow" },
  ],
  report_definitions: [
    { name: "MRR trend" },
    { name: "Churn analysis" },
  ],
  delivery_schedule: {
    cron_expression: "0 8 1 * *",
    channel_type: "EMAIL",
  },
}

async function mockOnboardingApi(
  page: Page,
  initialState: OnboardingStatePayload,
): Promise<void> {
  let state = { ...initialState }

  await page.route("**/api/v1/onboarding/state", async (route) => {
    const method = route.request().method()
    if (method === "GET") {
      await fulfillJson(route, apiResponse(state))
      return
    }
    if (method === "PATCH") {
      const payload = (route.request().postDataJSON() ?? {}) as {
        current_step?: number
        industry?: string
        erp_connected?: boolean
      }
      if (payload.current_step !== undefined) {
        state.current_step = payload.current_step
      }
      if (payload.industry !== undefined) {
        state.industry = payload.industry
      }
      if (payload.erp_connected !== undefined) {
        state.erp_connected = payload.erp_connected
      }
      await fulfillJson(route, apiResponse(state))
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/onboarding/templates", async (route) => {
    if (route.request().url().includes("/templates/")) {
      await route.continue()
      return
    }
    await fulfillJson(
      route,
      apiResponse([
        {
          id: "saas",
          name: "SaaS / Subscription",
          industry: "saas",
          description: "Template",
          board_pack_sections_count: 2,
          report_definitions_count: 2,
        },
      ]),
    )
  })

  await page.route("**/api/v1/onboarding/templates/*", async (route) => {
    await fulfillJson(route, apiResponse(templateDetail))
  })

  await page.route("**/api/v1/onboarding/apply", async (route) => {
    state.template_applied = true
    state.template_id = "saas"
    state.current_step = 3
    await fulfillJson(
      route,
      apiResponse({
        board_pack_definition_id: "def-1",
        report_definition_ids: ["rep-1", "rep-2"],
        delivery_schedule_id: "sched-1",
        step: 3,
      }),
    )
  })

  await page.route("**/api/v1/onboarding/complete", async (route) => {
    state.completed = true
    state.current_step = 5
    await fulfillJson(route, apiResponse(state))
  })
}

test.describe("Onboarding wizard", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("test_onboarding_page_loads", async ({ page }) => {
    await mockOnboardingApi(page, baseState())
    await page.goto("/onboarding")
    await expect(page.getByText("Let's set up your workspace")).toBeVisible()
  })

  test("test_industry_selection", async ({ page }) => {
    await mockOnboardingApi(page, baseState())
    await page.goto("/onboarding")

    const continueButton = page.getByRole("button", { name: "Continue" })
    await expect(continueButton).toBeDisabled()

    await page.getByRole("button", { name: "SaaS" }).click()
    await expect(continueButton).toBeEnabled()
  })

  test("test_step_navigation_forward", async ({ page }) => {
    await mockOnboardingApi(page, baseState())
    await page.goto("/onboarding")

    await page.getByRole("button", { name: "SaaS" }).click()
    await page.getByRole("button", { name: "Continue" }).click()

    await expect(page.getByText("Template preview")).toBeVisible()
  })

  test("test_template_preview_shows_sections", async ({ page }) => {
    const state = baseState()
    state.current_step = 2
    state.industry = "saas"
    await mockOnboardingApi(page, state)

    await page.goto("/onboarding")
    await expect(page.getByText("Board pack sections")).toBeVisible()
    await expect(page.getByText("P&L")).toBeVisible()
    await expect(page.getByText("MRR trend")).toBeVisible()
  })

  test("test_apply_template_success", async ({ page }) => {
    const state = baseState()
    state.current_step = 3
    state.industry = "saas"
    await mockOnboardingApi(page, state)

    await page.goto("/onboarding")
    await expect(page.getByText("Applying template")).toBeVisible()
    await expect(page.getByText("Board pack definition created")).toBeVisible()
    await expect(page.getByRole("button", { name: "Continue" })).toBeEnabled()
  })

  test("test_step4_erp_connect_links", async ({ page }) => {
    const state = baseState()
    state.current_step = 4
    state.industry = "saas"
    await mockOnboardingApi(page, state)

    await page.goto("/onboarding")

    const providers = ["Zoho Books", "Tally", "QuickBooks", "Xero", "SAP", "Oracle"]
    for (const provider of providers) {
      await expect(page.getByText(provider)).toBeVisible()
    }
    const links = page.getByRole("link", { name: "Connect" })
    await expect(links).toHaveCount(6)
    const hrefs = await links.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("href") ?? ""),
    )
    for (const href of hrefs) {
      expect(href.startsWith("/sync?erp=")).toBeTruthy()
    }
  })

  test("test_step4_skip_advances_to_step5", async ({ page }) => {
    const state = baseState()
    state.current_step = 4
    state.industry = "saas"
    await mockOnboardingApi(page, state)

    await page.goto("/onboarding")
    await page.getByRole("button", { name: "Skip for now" }).click()
    await expect(page.getByText("You're all set!")).toBeVisible()
  })

  test("test_step5_cta_links", async ({ page }) => {
    const state = baseState()
    state.current_step = 5
    state.industry = "saas"
    state.template_applied = true
    await mockOnboardingApi(page, state)

    await page.goto("/onboarding")
    await expect(page.getByRole("link", { name: "View your board pack" })).toHaveAttribute("href", "/board-pack")
    await expect(page.getByRole("link", { name: "Explore reports" })).toHaveAttribute("href", "/reports")
  })
})
