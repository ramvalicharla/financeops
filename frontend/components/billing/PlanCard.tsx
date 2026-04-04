"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/ConfirmDialog"
import { Dialog } from "@/components/ui/Dialog"
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

  if (!subscription) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Subscription not available.</p>
      </section>
    )
  }

  const resolvedPlan =
    subscription.plan ??
    plans.find((plan) => plan.id === subscription.plan_id) ??
    null
  const showINR = subscription.billing_country.toUpperCase() === "IN"
  const planPrice = resolvedPlan
    ? showINR
      ? formatINR(resolvedPlan.base_price_inr)
      : `$${resolvedPlan.base_price_usd}`
    : "-"

  return (
    <>
      <section className="space-y-4 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {(resolvedPlan?.plan_tier ?? "unknown").toUpperCase()}
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
        <Dialog open={showUpgradeModal} onClose={() => setShowUpgradeModal(false)} title="Upgrade plan" size="sm">
          <div className="space-y-3">
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
        </Dialog>
      ) : null}

      {showCancelModal ? (
        <ConfirmDialog
          open={showCancelModal}
          title="Cancel subscription"
          description="Your subscription will remain active until the end of the current billing period. You will lose access to premium features after that date."
          variant="destructive"
          confirmLabel="Cancel subscription"
          cancelLabel="Keep subscription"
          isLoading={isCancelling}
          onCancel={() => {
            setShowCancelModal(false)
          }}
          onConfirm={() => {
            void onCancel().then(() => {
              setShowCancelModal(false)
            })
          }}
        />
      ) : null}
    </>
  )
}
