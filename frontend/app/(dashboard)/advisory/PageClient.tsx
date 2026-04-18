"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { BriefcaseBusiness, PieChart, Search } from "lucide-react"
import { listFDDEngagements } from "@/lib/api/fdd"
import { listMAWorkspaces } from "@/lib/api/ma"
import { listPPAEngagements } from "@/lib/api/ppa"

interface ActivityItem {
  label: string
  href: string
  status: string
}

export default function AdvisoryHubPage() {
  const [activity, setActivity] = useState<ActivityItem[]>([])

  useEffect(() => {
    const load = async () => {
      const [fdd, ppa, ma] = await Promise.all([
        listFDDEngagements({ limit: 3, offset: 0 }),
        listPPAEngagements({ limit: 3, offset: 0 }),
        listMAWorkspaces({ limit: 3, offset: 0 }),
      ])

      const rows: ActivityItem[] = [
        ...fdd.data.map((row) => ({
          label: `FDD · ${row.engagement_name}`,
          href: `/advisory/fdd/${row.id}`,
          status: row.status,
        })),
        ...ppa.data.map((row) => ({
          label: `PPA · ${row.engagement_name}`,
          href: `/advisory/ppa/${row.id}`,
          status: row.status,
        })),
        ...ma.data.map((row) => ({
          label: `M&A · ${row.deal_codename}`,
          href: `/advisory/ma/${row.id}`,
          status: row.deal_status,
        })),
      ]
      setActivity(rows.slice(0, 9))
    }
    void load()
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Advisory Services</h1>
        <p className="text-sm text-muted-foreground">Premium analysis powered by your financial data</p>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="rounded-xl border border-border bg-card p-4">
          <Search className="h-5 w-5 text-[hsl(var(--brand-primary))]" />
          <h2 className="mt-2 text-base font-semibold text-foreground">Financial Due Diligence (FDD)</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Quality of Earnings, working capital analysis, debt review, and headcount normalisation.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">2,500 credits per engagement</p>
          <Link href="/advisory/fdd" className="mt-3 inline-flex text-sm text-[hsl(var(--brand-primary))]">
            Start FDD
          </Link>
        </article>

        <article className="rounded-xl border border-border bg-card p-4">
          <PieChart className="h-5 w-5 text-[hsl(var(--brand-primary))]" />
          <h2 className="mt-2 text-base font-semibold text-foreground">Purchase Price Allocation (PPA)</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            IFRS 3 / ASC 805 compliant intangible asset identification and fair value allocation.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">2,000 credits per engagement</p>
          <Link href="/advisory/ppa" className="mt-3 inline-flex text-sm text-[hsl(var(--brand-primary))]">
            Start PPA
          </Link>
        </article>

        <article className="rounded-xl border border-border bg-card p-4">
          <BriefcaseBusiness className="h-5 w-5 text-[hsl(var(--brand-primary))]" />
          <h2 className="mt-2 text-base font-semibold text-foreground">M&A Workspace</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Deal room, valuation engine, DD tracker, and document vault for live transactions.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">1,000 credits per month</p>
          <Link href="/advisory/ma" className="mt-3 inline-flex text-sm text-[hsl(var(--brand-primary))]">
            Open Workspace
          </Link>
        </article>
      </section>

      <section className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">Recent Activity</h3>
        </div>
        <div className="divide-y divide-border/60">
          {activity.map((row) => (
            <div key={`${row.label}-${row.href}`} className="flex items-center justify-between px-4 py-3">
              <Link href={row.href} className="text-sm text-foreground">
                {row.label}
              </Link>
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {row.status}
              </span>
            </div>
          ))}
          {activity.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">No advisory activity yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
