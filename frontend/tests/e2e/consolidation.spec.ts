import { expect, test, type Page } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const orgSetupSummary = {
  group: {
    id: "group-001",
    group_name: "Acme Group",
    reporting_currency: "INR",
  },
  entities: [
    { id: "entity-001", legal_name: "Acme India", cp_entity_id: "cp-001" },
    { id: "entity-002", legal_name: "Acme US", cp_entity_id: "cp-002" },
  ],
}

const consolidationSummary = {
  summary: {
    org_group_id: "group-001",
    group_name: "Acme Group",
    as_of_date: "2026-03-31",
    from_date: null,
    to_date: null,
    reporting_currency: "INR",
    entity_count: 2,
    elimination_count: 1,
    total_eliminations: "75000.00",
    minority_interest_placeholder: "25000.00",
  },
  hierarchy: {
    root_cp_entity_id: "cp-001",
    rows: [
      {
        org_entity_id: "entity-001",
        cp_entity_id: "cp-001",
        legal_name: "Acme India",
        parent_entity_id: null,
        ownership_pct: "100.0000",
        ownership_factor: "1.0000",
        consolidation_method: "FULL",
        weighted_debit: "0.00",
        weighted_credit: "0.00",
        weighted_balance: "0.00",
      },
      {
        org_entity_id: "entity-002",
        cp_entity_id: "cp-002",
        legal_name: "Acme US",
        parent_entity_id: "entity-001",
        ownership_pct: "75.0000",
        ownership_factor: "0.7500",
        consolidation_method: "FULL",
        weighted_debit: "0.00",
        weighted_credit: "0.00",
        weighted_balance: "0.00",
      },
    ],
  },
  statements: {
    trial_balance: {
      rows: [
        {
          account_code: "4000",
          account_name: "Revenue",
          debit_sum: "0.00",
          credit_sum: "4500000.00",
          balance: "-4500000.00",
        },
      ],
      total_debit: "4500000.00",
      total_credit: "4500000.00",
      is_balanced: true,
    },
    pnl: null,
    balance_sheet: null,
  },
  elimination_summary: [
    {
      elimination_type: "Intercompany Revenue",
      amount: "75000.00",
    },
  ],
}

const runAccepted = {
  run_id: "run-001",
  workflow_id: "wf-001",
  status: "accepted",
  correlation_id: "corr-001",
}

const runDetails = {
  run_id: "run-001",
  status: "completed",
  event_seq: 12,
  event_time: "2026-03-31T23:59:59Z",
  workflow_id: "wf-001",
  configuration: {
    org_group_id: "group-001",
    as_of_date: "2026-03-31",
  },
  summary: consolidationSummary.summary,
}

const runStatements = {
  run_id: "run-001",
  status: "completed",
  statements: consolidationSummary.statements,
  elimination_summary: consolidationSummary.elimination_summary,
  eliminations: [],
  hierarchy: consolidationSummary.hierarchy,
  summary: consolidationSummary.summary,
}

async function mockConsolidation(page: Page): Promise<void> {
  await mockCSRF(page)
  await mockSession(page)

  await page.route("**/api/v1/org-setup/summary", async (route) => {
    await fulfillJson(route, apiResponse(orgSetupSummary))
  })

  await page.route("**/api/v1/consolidation/summary?**", async (route) => {
    await fulfillJson(route, apiResponse(consolidationSummary))
  })

  await page.route("**/api/v1/consolidation/run", async (route) => {
    await fulfillJson(route, apiResponse(runAccepted))
  })

  await page.route("**/api/v1/consolidation/runs/run-001/statements", async (route) => {
    await fulfillJson(route, apiResponse(runStatements))
  })

  await page.route("**/api/v1/consolidation/runs/run-001", async (route) => {
    await fulfillJson(route, apiResponse(runDetails))
  })
}

test.describe("Consolidation page", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
  })

  test("consolidation page loads the current summary contract", async ({ page }) => {
    await mockConsolidation(page)

    await page.goto("/consolidation")

    await expect(page.getByRole("heading", { name: "Consolidation Engine" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Summary", exact: true })).toBeVisible()
    await expect(page.getByText("Entities", { exact: true })).toBeVisible()
    await expect(page.getByText("2", { exact: true })).toBeVisible()
    await expect(page.getByRole("cell", { name: "Acme India" })).toBeVisible()
    await expect(page.getByRole("cell", { name: "Acme US" })).toBeVisible()
  })

  test("run consolidation redirects to the run details page", async ({ page }) => {
    await mockConsolidation(page)

    await page.goto("/consolidation")
    await page.getByRole("button", { name: "Run Consolidation" }).click()

    await page.waitForURL("**/consolidation/runs/run-001")
    await expect(page.getByRole("heading", { name: "Consolidation Run" })).toBeVisible()
    await expect(page.getByText("run-001")).toBeVisible()
    await expect(page.getByRole("heading", { name: "Trial Balance", exact: true })).toBeVisible()
  })

  test("run details show elimination summary and trial balance rows", async ({ page }) => {
    await mockConsolidation(page)

    await page.goto("/consolidation/runs/run-001")

    await expect(page.getByText("Elimination Summary")).toBeVisible()
    await expect(page.getByRole("cell", { name: "Intercompany Revenue" })).toBeVisible()
    await expect(page.getByRole("cell", { name: "4000" })).toBeVisible()
    await expect(page.getByRole("cell", { name: "Revenue", exact: true })).toBeVisible()
  })

  test("error state", async ({ page }) => {
    await mockCSRF(page)
    await mockSession(page)

    await page.route("**/api/v1/org-setup/summary", async (route) => {
      await fulfillJson(route, apiResponse(orgSetupSummary))
    })

    await page.route("**/api/v1/consolidation/summary?**", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "failed" },
          meta: { request_id: "req-con", timestamp: new Date().toISOString() },
        },
        500,
      )
    })

    await page.goto("/consolidation")
    await expect(page.getByText("Failed to load consolidation summary.")).toBeVisible()
    await expectNotCrashed(page)
  })
})
