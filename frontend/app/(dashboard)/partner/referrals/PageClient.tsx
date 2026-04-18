"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { listPartnerReferrals } from "@/lib/api/partner"
import type { ReferralTrackingRow } from "@/lib/types/partner"
import { ReferralCard } from "@/components/partner/ReferralCard"

export default function PartnerReferralsPage() {
  const [rows, setRows] = useState<ReferralTrackingRow[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const payload = await listPartnerReferrals({ limit: 100, offset: 0 })
      setRows(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load referrals")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const funnel = useMemo(() => {
    return {
      clicked: rows.filter((row) => row.status === "clicked").length,
      signedUp: rows.filter((row) => row.status === "signed_up").length,
      converted: rows.filter((row) => row.status === "converted").length,
    }
  }, [rows])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Referrals</h1>
        <p className="text-sm text-muted-foreground">Track click, signup, and conversion progression.</p>
      </header>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Clicked</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{funnel.clicked}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Signed Up</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{funnel.signedUp}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Converted</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{funnel.converted}</p>
        </div>
      </section>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-3">
        {rows.map((row) => (
          <ReferralCard key={row.id} referral={row} />
        ))}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No referrals tracked yet.</p>
        ) : null}
      </section>
    </div>
  )
}
