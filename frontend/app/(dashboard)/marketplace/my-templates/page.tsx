"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { getMarketplaceContributorDashboard } from "@/lib/api/marketplace"
import type {
  MarketplacePayout,
  MarketplacePurchase,
  MarketplaceTemplate,
} from "@/lib/types/marketplace"
import { ContributorDashboard } from "@/components/marketplace/ContributorDashboard"
import { TemplateCard } from "@/components/marketplace/TemplateCard"

type TabKey = "published" | "pending_review" | "draft" | "rejected"

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "published", label: "Published" },
  { key: "pending_review", label: "Pending Review" },
  { key: "draft", label: "Draft" },
  { key: "rejected", label: "Rejected" },
]

export default function MarketplaceMyTemplatesPage() {
  const [tab, setTab] = useState<TabKey>("published")
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([])
  const [earningsThisMonth, setEarningsThisMonth] = useState("0")
  const [earningsTotal, setEarningsTotal] = useState("0")
  const [recentPurchases, setRecentPurchases] = useState<MarketplacePurchase[]>([])
  const [payoutHistory, setPayoutHistory] = useState<MarketplacePayout[]>([])
  const [hasContributor, setHasContributor] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const payload = await getMarketplaceContributorDashboard()
      setHasContributor(true)
      setTemplates(payload.templates)
      setEarningsThisMonth(payload.earnings_this_month)
      setEarningsTotal(payload.earnings_total)
      setRecentPurchases(payload.recent_purchases)
      setPayoutHistory(payload.payout_history)
    } catch (loadError) {
      setHasContributor(false)
      setTemplates([])
      setError(loadError instanceof Error ? loadError.message : "Unable to load contributor dashboard")
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const visibleTemplates = useMemo(
    () => templates.filter((template) => template.status === tab),
    [tab, templates],
  )

  if (!hasContributor) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">My Templates</h1>
        <p className="text-sm text-muted-foreground">
          Register as a contributor first to manage templates and view earnings.
        </p>
        <Link
          href="/marketplace/contribute"
          className="inline-flex rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Open Contributor Portal
        </Link>
        {error ? <p className="text-xs text-muted-foreground">{error}</p> : null}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">My Templates</h1>
          <p className="text-sm text-muted-foreground">Manage submissions and contributor earnings.</p>
        </div>
        <Link
          href="/marketplace/contribute"
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Submit New Template
        </Link>
      </header>

      <ContributorDashboard
        earningsThisMonth={earningsThisMonth}
        earningsTotal={earningsTotal}
        templates={templates}
        recentPurchases={recentPurchases}
        payouts={payoutHistory}
      />

      <section className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={`rounded-full border px-3 py-1 text-xs ${
                tab === item.key
                  ? "border-[hsl(var(--brand-primary))] text-foreground"
                  : "border-border text-muted-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleTemplates.map((template) => (
            <TemplateCard key={template.id} template={template} />
          ))}
        </div>
        {visibleTemplates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No templates in this status.</p>
        ) : null}
      </section>
    </div>
  )
}
