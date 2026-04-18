"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { createPPAEngagement, listPPAEngagements } from "@/lib/api/ppa"
import type { PPAEngagement } from "@/lib/types/ppa"

export default function PPAPage() {
  const [rows, setRows] = useState<PPAEngagement[]>([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const payload = await listPPAEngagements({ limit: 50, offset: 0 })
      setRows(payload.data)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load PPA engagements")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const createNew = async () => {
    setCreating(true)
    setError(null)
    try {
      await createPPAEngagement({
        engagement_name: `PPA ${new Date().toISOString().slice(0, 10)}`,
        target_company_name: "Target Company",
        acquisition_date: new Date().toISOString().slice(0, 10),
        purchase_price: "1000000.00",
        purchase_price_currency: "INR",
        accounting_standard: "IFRS3",
      })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create PPA engagement")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Purchase Price Allocation</h1>
          <p className="text-sm text-muted-foreground">2,000 credits per engagement</p>
        </div>
        <button
          type="button"
          onClick={createNew}
          disabled={creating}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
        >
          {creating ? "Creating..." : "New PPA"}
        </button>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {rows.map((row) => (
          <article key={row.id} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-foreground">{row.engagement_name}</h3>
                <p className="text-xs text-muted-foreground">{row.target_company_name}</p>
              </div>
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {row.status}
              </span>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">Purchase price: {row.purchase_price} {row.purchase_price_currency}</p>
            <Link href={`/advisory/ppa/${row.id}`} className="mt-3 inline-flex text-sm text-[hsl(var(--brand-primary))]">
              Open
            </Link>
          </article>
        ))}
        {rows.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No PPA engagements yet.
          </div>
        ) : null}
      </section>
    </div>
  )
}
