"use client"

import type { MarketplacePayout, MarketplacePurchase, MarketplaceTemplate } from "@/lib/types/marketplace"

interface ContributorDashboardProps {
  earningsThisMonth: string
  earningsTotal: string
  templates: MarketplaceTemplate[]
  recentPurchases: MarketplacePurchase[]
  payouts: MarketplacePayout[]
}

export function ContributorDashboard({
  earningsThisMonth,
  earningsTotal,
  templates,
  recentPurchases,
  payouts,
}: ContributorDashboardProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">This Month</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{earningsThisMonth} credits</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Total Earnings</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{earningsTotal} credits</p>
        </div>
      </div>

      <section className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">Recent Purchases</h3>
        </div>
        <div className="divide-y divide-border/60">
          {recentPurchases.map((row) => (
            <div key={row.id} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="text-muted-foreground">{row.purchased_at.slice(0, 10)}</span>
              <span className="text-foreground">{row.contributor_share_credits} credits</span>
            </div>
          ))}
          {recentPurchases.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">No purchases yet.</p>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">Payout History</h3>
        </div>
        <div className="divide-y divide-border/60">
          {payouts.map((row) => (
            <div key={row.id} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="text-muted-foreground">
                {row.period_start} to {row.period_end}
              </span>
              <span className="text-foreground">${row.total_usd_amount}</span>
            </div>
          ))}
          {payouts.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">No payouts yet.</p>
          ) : null}
        </div>
      </section>

      <p className="text-xs text-muted-foreground">Templates managed: {templates.length}</p>
    </div>
  )
}

