"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { getConsentSummary, listBreaches } from "@/lib/api/compliance"
import type { ConsentSummary, GDPRBreach } from "@/lib/types/compliance"
import { ConsentCoverageTable } from "@/components/trust/ConsentCoverageTable"

export default function TrustGdprPage() {
  const [summary, setSummary] = useState<ConsentSummary | null>(null)
  const [breaches, setBreaches] = useState<GDPRBreach[]>([])

  useEffect(() => {
    const load = async () => {
      const [summaryData, breachesData] = await Promise.all([
        getConsentSummary(),
        listBreaches({ limit: 100, offset: 0 }),
      ])
      setSummary(summaryData)
      setBreaches(breachesData.data)
    }
    void load()
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">GDPR Compliance</h1>
        <p className="text-sm text-muted-foreground">Tenant consent coverage, breach history, and data-rights operations.</p>
      </header>

      {summary ? <ConsentCoverageTable summary={summary} /> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Total Users</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{summary?.total_users ?? 0}</p>
        </article>
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Breach Count</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{breaches.length}</p>
        </article>
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Last Audit</p>
          <p className="mt-2 text-sm text-foreground">{new Date().toISOString().slice(0, 10)}</p>
        </article>
      </div>

      <div className="flex gap-3">
        <Link href="/trust/gdpr/consent" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Consent Coverage
        </Link>
        <Link href="/trust/gdpr/breach" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          View Breach History
        </Link>
      </div>
    </div>
  )
}

