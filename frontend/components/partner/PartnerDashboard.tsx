"use client"

import Link from "next/link"
import type { PartnerDashboard as PartnerDashboardPayload } from "@/lib/types/partner"

interface PartnerDashboardProps {
  dashboard: PartnerDashboardPayload
}

export function PartnerDashboard({ dashboard }: PartnerDashboardProps) {
  const stats = dashboard.stats

  const copyLink = async () => {
    if (!navigator?.clipboard) {
      return
    }
    await navigator.clipboard.writeText(dashboard.referral_link)
  }

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Referral Link</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <code className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground">
            {dashboard.referral_link}
          </code>
          <button
            type="button"
            onClick={() => void copyLink()}
            className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
          >
            Copy
          </button>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Clicks</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_clicks}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Signups</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_signups}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Conversions</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_conversions}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Conversion Rate</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{stats.conversion_rate}</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-foreground">Commissions</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Total earned: <span className="font-medium text-foreground">{stats.total_commissions_earned}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Pending: <span className="font-medium text-foreground">{stats.pending_commissions}</span>
        </p>
      </section>

      <section className="flex gap-2">
        <Link
          href="/partner/referrals"
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          View Referrals
        </Link>
        <Link
          href="/partner/earnings"
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          View Earnings
        </Link>
      </section>
    </div>
  )
}
