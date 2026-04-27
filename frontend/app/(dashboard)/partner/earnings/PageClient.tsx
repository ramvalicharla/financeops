"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { listPartnerCommissions } from "@/lib/api/partner"
import type { PartnerCommissionRow } from "@/lib/types/partner"
import { CommissionTable } from "@/components/partner/CommissionTable"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"

export default function PartnerEarningsPage() {
  const [commissions, setCommissions] = useState<PartnerCommissionRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const { fmt } = useFormattedAmount()

  const load = useCallback(async () => {
    setError(null)
    try {
      const payload = await listPartnerCommissions({ limit: 100, offset: 0 })
      setCommissions(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load commissions")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const totals = useMemo(() => {
    let earned = 0
    let pending = 0
    for (const row of commissions) {
      const amount = Number.parseFloat(row.commission_amount)
      earned += amount
      if (row.status === "pending") {
        pending += amount
      }
    }
    return { earned, pending }
  }, [commissions])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Partner Earnings</h1>
        <p className="text-sm text-muted-foreground">Commission history, status, and payout visibility.</p>
      </header>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Total Earned</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(totals.earned)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Pending Payout</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(totals.pending)}</p>
        </div>
      </section>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      <CommissionTable commissions={commissions} />
    </div>
  )
}
