"use client"

import Link from "next/link"
import { useCurrentSubscription, usePlans } from "@/hooks/useBilling"

export default function BillingPlansPage() {
  const plansQuery = usePlans()
  const subscriptionQuery = useCurrentSubscription()
  const currentPlanId = subscriptionQuery.data?.plan?.id ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Billing Plans</h1>
        <Link href="/billing" className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent">
          Back to Billing
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(plansQuery.data ?? []).map((plan) => {
          const isCurrent = currentPlanId === plan.id
          return (
            <div key={plan.id} className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">{plan.name ?? plan.plan_tier}</h2>
                {isCurrent ? (
                  <span className="rounded bg-[hsl(var(--brand-success)/0.2)] px-2 py-1 text-xs text-[hsl(var(--brand-success))]">
                    Current
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Tier: {plan.plan_tier}</p>
              <p className="text-sm text-muted-foreground">Cycle: {plan.billing_cycle}</p>
              <p className="text-sm text-muted-foreground">
                Price: {plan.price ?? plan.base_price_usd} {plan.currency ?? "USD"}
              </p>
              <p className="text-sm text-muted-foreground">Included credits: {plan.included_credits}</p>
            </div>
          )
        })}
      </div>

      {plansQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading plans...</p> : null}
      {plansQuery.isError ? <p className="text-sm text-destructive">Failed to load plans.</p> : null}
    </div>
  )
}
