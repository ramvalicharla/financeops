"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import {
  getMarketplaceStats,
  listMarketplacePending,
  processMarketplacePayouts,
  reviewMarketplaceTemplate,
} from "@/lib/api/marketplace"
import type { MarketplaceContributor, MarketplaceTemplate } from "@/lib/types/marketplace"

interface MarketplaceStats {
  total_templates: number
  published_templates: number
  total_revenue_credits: number
  top_contributors: MarketplaceContributor[]
}

export default function AdminMarketplacePage() {
  const [pending, setPending] = useState<MarketplaceTemplate[]>([])
  const [stats, setStats] = useState<MarketplaceStats | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const [pendingPayload, statsPayload] = await Promise.all([
        listMarketplacePending({ limit: 100, offset: 0 }),
        getMarketplaceStats(),
      ])
      setPending(pendingPayload.data)
      setStats(statsPayload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load marketplace admin data")
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const review = async (templateId: string, action: "approve" | "reject") => {
    setMessage(null)
    setError(null)
    try {
      await reviewMarketplaceTemplate(templateId, { action })
      setMessage(`Template ${action}d.`)
      await load()
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Failed to review template")
    }
  }

  const processPayouts = async () => {
    setMessage(null)
    setError(null)
    try {
      const payload = await processMarketplacePayouts()
      setMessage(`Payout processing complete. ${payload.count} payout records created.`)
      await load()
    } catch (payoutError) {
      setError(payoutError instanceof Error ? payoutError.message : "Failed to process payouts")
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Marketplace Admin</h1>
          <p className="text-sm text-muted-foreground">Review template submissions and manage marketplace payouts.</p>
        </div>
        <button
          type="button"
          onClick={() => void processPayouts()}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Process Payouts
        </button>
      </header>

      {stats ? (
        <section className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Total Templates</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_templates}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Published</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.published_templates}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Revenue (credits)</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_revenue_credits}</p>
          </div>
        </section>
      ) : null}

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Pending Review Queue</h2>
        </div>
        <div className="divide-y divide-border/60">
          {pending.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-foreground">{row.title}</p>
                <p className="text-xs text-muted-foreground">{row.template_type} | {row.price_credits} credits</p>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href={`/marketplace/${row.id}`}
                  className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
                >
                  Preview
                </Link>
                <button
                  type="button"
                  onClick={() => void review(row.id, "approve")}
                  className="rounded-md border border-emerald-500/50 px-2 py-1 text-xs text-emerald-200"
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => void review(row.id, "reject")}
                  className="rounded-md border border-[hsl(var(--brand-danger)/0.5)] px-2 py-1 text-xs text-[hsl(var(--brand-danger))]"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
          {pending.length === 0 ? (
            <p className="px-4 py-4 text-sm text-muted-foreground">No templates pending review.</p>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Top Contributors</h2>
        <div className="mt-3 space-y-2">
          {stats?.top_contributors.map((row) => (
            <div key={row.id} className="flex items-center justify-between text-sm">
              <span className="text-foreground">{row.display_name}</span>
              <span className="text-muted-foreground">{row.total_earnings} credits</span>
            </div>
          ))}
          {(stats?.top_contributors.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">No contributor earnings yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
