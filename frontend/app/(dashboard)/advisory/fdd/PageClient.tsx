"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { EngagementCard } from "@/components/advisory/fdd/EngagementCard"
import { createFDDEngagement, listFDDEngagements } from "@/lib/api/fdd"
import type { FDDEngagement } from "@/lib/types/fdd"

const defaultSections = [
  "quality_of_earnings",
  "working_capital",
  "debt_liability",
  "headcount",
  "revenue_quality",
]

export default function FDDPage() {
  const router = useRouter()
  const [rows, setRows] = useState<FDDEngagement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listFDDEngagements({ limit: 50, offset: 0 })
      setRows(payload.data)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load FDD engagements")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const createNew = async () => {
    setCreating(true)
    setError(null)
    try {
      const today = new Date()
      const end = today.toISOString().slice(0, 10)
      const startDate = new Date(today)
      startDate.setFullYear(startDate.getFullYear() - 1)
      const start = startDate.toISOString().slice(0, 10)
      const engagement = await createFDDEngagement({
        engagement_name: `FDD Engagement ${today.toISOString().slice(0, 10)}`,
        target_company_name: "Target Company",
        analysis_period_start: start,
        analysis_period_end: end,
        sections_requested: defaultSections,
      })
      router.push(`/advisory/fdd/${engagement.id}`)
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create engagement")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Financial Due Diligence</h1>
          <p className="text-sm text-muted-foreground">2,500 credits per engagement</p>
        </div>
        <button
          type="button"
          disabled={creating}
          onClick={createNew}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
        >
          {creating ? "Creating..." : "New FDD Engagement"}
        </button>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <div className="h-40 animate-pulse rounded-xl bg-muted" /> : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {rows.map((engagement) => (
          <EngagementCard key={engagement.id} engagement={engagement} />
        ))}
        {!loading && rows.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No FDD engagements yet.
          </div>
        ) : null}
      </section>
    </div>
  )
}
