"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus"
import { formatINR } from "@/lib/utils"
import type { BillingCycle, BillingPlan, TenantSubscription } from "@/types/billing"

interface PlanCardProps {
  subscription: TenantSubscription | null
  plans: BillingPlan[]
  onUpgrade: (planId: string, cycle: BillingCycle) => Promise<void>
  onCancel: () => Promise<void>
  isUpgrading: boolean
  isCancelling: boolean
}

export function PlanCard({
  subscription,
  plans,
  onUpgrade,
  onCancel,
  isUpgrading,
  isCancelling,
}: PlanCardProps) {
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [showCancelModal, setShowCancelModal] = useState(false)
  const [selectedPlanId, setSelectedPlanId] = useState<string>("")
  const [selectedCycle, setSelectedCycle] = useState<BillingCycle>("monthly")
  const [cancelText, setCancelText] = useState("")

  if (!subscription) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Subscription not available.</p>
      </section>
    )
  }

  const showINR = subscription.billing_country.toUpperCase() === "IN"
  const planPrice = showINR
    ? formatINR(subscription.plan.base_price_inr)
    : `$${subscription.plan.base_price_usd}`

  return (
    <>
      <section className="space-y-4 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {subscription.plan.plan_tier.toUpperCase()}
            </h3>
            <p className="text-sm text-muted-foreground">
              {planPrice} / {subscription.billing_cycle}
            </p>
          </div>
          <SubscriptionStatus status={subscription.status} />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Billing cycle
            </p>
            <p className="text-sm text-foreground">
              {subscription.billing_cycle === "annual" ? "Annual" : "Monthly"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Next billing date
            </p>
            <p className="text-sm text-foreground">
              {new Date(subscription.current_period_end).toLocaleDateString()}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Provider
            </p>
            <p className="text-sm text-foreground">{subscription.provider}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setShowUpgradeModal(true)}>
            Upgrade Plan
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => setShowCancelModal(true)}
          >
            Cancel Subscription
          </Button>
        </div>
      </section>

      {showUpgradeModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-5">
            <h4 className="text-lg font-semibold text-foreground">Upgrade plan</h4>
            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-sm text-foreground">Plan</label>
                <select
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
                  value={selectedPlanId}
                  onChange={(event) => setSelectedPlanId(event.target.value)}
                >
                  <option value="">Select plan</option>
                  {plans.map((plan) => (
                    <option key={plan.id} value={plan.id}>
                      {plan.plan_tier.toUpperCase()} -{" "}
                      {showINR ? formatINR(plan.base_price_inr) : `$${plan.base_price_usd}`}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-foreground">Billing cycle</label>
                <select
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
                  value={selectedCycle}
                  onChange={(event) =>
                    setSelectedCycle(event.target.value as BillingCycle)
                  }
                >
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual</option>
                </select>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowUpgradeModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={!selectedPlanId || isUpgrading}
                onClick={() => {
                  void onUpgrade(selectedPlanId, selectedCycle).then(() =>
                    setShowUpgradeModal(false),
                  )
                }}
              >
                {isUpgrading ? "Updating..." : "Confirm Upgrade"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {showCancelModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-5">
            <h4 className="text-lg font-semibold text-foreground">
              Confirm cancellation
            </h4>
            <p className="mt-2 text-sm text-muted-foreground">
              Type <strong>CANCEL</strong> to confirm cancellation.
            </p>
            <input
              className="mt-3 w-full rounded border border-border bg-background px-3 py-2 text-sm"
              value={cancelText}
              onChange={(event) => setCancelText(event.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setCancelText("")
                  setShowCancelModal(false)
                }}
              >
                Back
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={cancelText !== "CANCEL" || isCancelling}
                onClick={() => {
                  void onCancel().then(() => {
                    setCancelText("")
                    setShowCancelModal(false)
                  })
                }}
              >
                {isCancelling ? "Cancelling..." : "Confirm Cancellation"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
