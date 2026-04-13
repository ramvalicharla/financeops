import { expect, test } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  expectNotCrashed,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

const basePlan = {
  id: "plan-pro-monthly",
  plan_tier: "professional" as const,
  billing_cycle: "monthly" as const,
  base_price_inr: "4999.00",
  base_price_usd: "79.00",
  included_credits: 1000,
  max_entities: 10,
  max_connectors: 20,
  trial_days: 14,
  annual_discount_pct: "10.00",
}

const activeSubscription = {
  id: "sub-1",
  plan: basePlan,
  status: "active" as const,
  billing_cycle: "monthly" as const,
  current_period_start: "2026-03-01",
  current_period_end: "2026-03-31",
  trial_end: null,
  billing_country: "IN",
  billing_currency: "INR",
  provider: "razorpay" as const,
}

const invoices = [
  {
    id: "inv-1",
    provider_invoice_id: "INV-001",
    status: "paid" as const,
    currency: "INR",
    total: "5000.00",
    due_date: "2026-03-10",
    paid_at: "2026-03-08T10:00:00Z",
    invoice_pdf_url: "https://example.com/invoice/1.pdf",
    created_at: "2026-03-01T00:00:00Z",
  },
  {
    id: "inv-2",
    provider_invoice_id: "INV-002",
    status: "open" as const,
    currency: "INR",
    total: "4500.00",
    due_date: "2026-02-10",
    paid_at: null,
    invoice_pdf_url: "https://example.com/invoice/2.pdf",
    created_at: "2026-02-01T00:00:00Z",
  },
  {
    id: "inv-3",
    provider_invoice_id: "INV-003",
    status: "draft" as const,
    currency: "INR",
    total: "4200.00",
    due_date: "2026-01-10",
    paid_at: null,
    invoice_pdf_url: null,
    created_at: "2026-01-01T00:00:00Z",
  },
]

test.describe("Billing page", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("Billing page loads", async ({ page }) => {
    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(route, apiResponse(activeSubscription))
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([basePlan]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: 450,
        included_in_plan: 1000,
        used_this_period: 550,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([
        {
          id: "txn-1",
          transaction_type: "consumption",
          credits_delta: -100,
          credits_balance_after: 450,
          description: "Sync run usage",
          created_at: "2026-03-01T10:00:00Z",
        },
      ]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse(invoices))
    })

    await page.goto("/billing")
    await expect(page.getByText("PROFESSIONAL")).toBeVisible()
    await expect(page.getByText("450").first()).toBeVisible()
    await expect(page.locator("table").nth(1).locator("tbody tr")).toHaveCount(3)
  })

  test("Suspended account banner", async ({ page }) => {
    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(route, apiResponse({ ...activeSubscription, status: "suspended" }))
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([basePlan]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: 450,
        included_in_plan: 1000,
        used_this_period: 550,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/billing")
    await expect(
      page.getByText("Account suspended. Update payment method to restore access."),
    ).toBeVisible()
  })

  test("Grace period banner", async ({ page }) => {
    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(route, apiResponse({ ...activeSubscription, status: "grace_period" }))
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([basePlan]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: 450,
        included_in_plan: 1000,
        used_this_period: 550,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/billing")
    await expect(page.getByText("Account in grace period.")).toBeVisible()
  })

  test("Top-up credits", async ({ page }) => {
    let currentBalance = 450

    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(route, apiResponse(activeSubscription))
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([basePlan]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: currentBalance,
        included_in_plan: 1000,
        used_this_period: 550,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse(invoices))
    })
    await page.route("**/api/v1/billing/credits/top-up", async (route) => {
      const body = route.request().postDataJSON() as { credits?: number }
      currentBalance += body.credits ?? 0
      await fulfillJson(route, apiResponse({ success: true }))
    })

    await page.goto("/billing")
    await page.getByRole("button", { name: "Buy More Credits" }).click()
    const topUpDialog = page.getByRole("dialog", { name: "Add credits" })
    await expect(topUpDialog).toBeVisible()
    await topUpDialog.getByRole("button", { name: "500 Credits" }).click()
    await topUpDialog.getByRole("button", { name: "Confirm Top-up" }).click()
    await expect(topUpDialog).not.toBeVisible()
    await expect(page.getByText("950").first()).toBeVisible()
  })

  test("Cancel subscription confirmation", async ({ page }) => {
    let cancelRequested = false
    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(route, apiResponse(activeSubscription))
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([basePlan]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: 450,
        included_in_plan: 1000,
        used_this_period: 550,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse(invoices))
    })
    await page.route("**/api/v1/billing/subscriptions/cancel", async (route) => {
      cancelRequested = true
      await fulfillJson(route, apiResponse({ success: true }))
    })

    await page.goto("/billing")
    await page.getByRole("button", { name: "Cancel Subscription" }).click()
    const cancelDialog = page.getByRole("dialog", { name: /Cancel subscription/i })
    await expect(cancelDialog).toBeVisible()
    await expect(
      cancelDialog.getByText(
        "Your subscription will remain active until the end of the current billing period.",
      ),
    ).toBeVisible()
    await cancelDialog.getByRole("button", { name: "Cancel subscription" }).click()
    await expect(cancelDialog).not.toBeVisible()
    expect(cancelRequested).toBeTruthy()
  })

  test("Error state", async ({ page }) => {
    await page.route("**/api/v1/billing/subscriptions/current", async (route) => {
      await fulfillJson(
        route,
        {
          data: null,
          error: { code: "server_error", message: "failed" },
          meta: { request_id: "req-billing", timestamp: new Date().toISOString() },
        },
        500,
      )
    })
    await page.route("**/api/v1/billing/plans", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/credits/balance", async (route) => {
      await fulfillJson(route, apiResponse({
        current_balance: 0,
        included_in_plan: 0,
        used_this_period: 0,
        expires_at: null,
      }))
    })
    await page.route("**/api/v1/billing/credits/ledger", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })
    await page.route("**/api/v1/billing/invoices", async (route) => {
      await fulfillJson(route, apiResponse([]))
    })

    await page.goto("/billing")
    await expect(page.getByText("Failed to load billing subscription details.")).toBeVisible()
    await expectNotCrashed(page)
  })
})
