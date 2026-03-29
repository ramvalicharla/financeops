"use client"

import { PlanCard } from "@/components/billing/PlanCard"
import { CreditBalance } from "@/components/billing/CreditBalance"
import { InvoiceTable } from "@/components/billing/InvoiceTable"
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus"
import {
  useCancelSubscription,
  useCreditBalance,
  useCreditLedger,
  useCurrentSubscription,
  useInvoices,
  usePlans,
  useTopUp,
  useUpgradeSubscription,
} from "@/hooks/useBilling"

export default function BillingPage() {
  const subscriptionQuery = useCurrentSubscription()
  const plansQuery = usePlans()
  const balanceQuery = useCreditBalance()
  const ledgerQuery = useCreditLedger()
  const invoicesQuery = useInvoices()
  const topUpMutation = useTopUp()
  const cancelMutation = useCancelSubscription()
  const upgradeMutation = useUpgradeSubscription()

  const subscription = subscriptionQuery.data ?? null
  const recentTransactions = (ledgerQuery.data ?? []).slice(0, 10)

  return (
    <div className="space-y-6">
      {subscriptionQuery.isError ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load billing subscription details.
        </div>
      ) : null}

      {subscription?.status === "suspended" ? (
        <div className="rounded-lg border border-[hsl(var(--brand-danger)/0.5)] bg-[hsl(var(--brand-danger)/0.2)] px-4 py-3 text-sm text-[hsl(var(--brand-danger))]">
          Account suspended. Update payment method to restore access.
        </div>
      ) : null}

      {subscription?.status === "grace_period" ? (
        <div className="rounded-lg border border-[hsl(var(--brand-warning)/0.5)] bg-[hsl(var(--brand-warning)/0.2)] px-4 py-3 text-sm text-[hsl(var(--brand-warning))]">
          Account in grace period. Please update payment method before{" "}
          {new Date(subscription.current_period_end).toLocaleDateString()}.
        </div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Current Plan</h2>
        {subscription ? <SubscriptionStatus status={subscription.status} /> : null}
        <PlanCard
          subscription={subscription}
          plans={plansQuery.data ?? []}
          isCancelling={cancelMutation.isPending}
          isUpgrading={upgradeMutation.isPending}
          onCancel={async () => {
            await cancelMutation.mutateAsync()
          }}
          onUpgrade={async (planId, cycle) => {
            await upgradeMutation.mutateAsync({ planId, cycle })
          }}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Credits</h2>
        <CreditBalance
          balance={balanceQuery.data ?? null}
          isLoading={topUpMutation.isPending}
          onTopUp={async (credits) => {
            await topUpMutation.mutateAsync(credits)
          }}
        />
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Last 10 Transactions
          </h3>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-3 py-2 text-left font-medium text-foreground">
                    Type
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Delta
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Balance After
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">
                    Description
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {recentTransactions.map((row) => (
                  <tr key={row.id} className="border-t border-border">
                    <td className="px-3 py-2 text-muted-foreground">
                      {row.transaction_type}
                    </td>
                    <td
                      className={`px-3 py-2 text-right ${
                        row.credits_delta >= 0
                          ? "text-[hsl(var(--brand-success))]"
                          : "text-[hsl(var(--brand-danger))]"
                      }`}
                    >
                      {row.credits_delta}
                    </td>
                    <td className="px-3 py-2 text-right text-muted-foreground">
                      {row.credits_balance_after}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {row.description}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {new Date(row.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {!recentTransactions.length ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-4 text-center text-muted-foreground"
                    >
                      No credit transactions yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Invoices</h2>
        <InvoiceTable invoices={invoicesQuery.data ?? []} />
      </section>
    </div>
  )
}
