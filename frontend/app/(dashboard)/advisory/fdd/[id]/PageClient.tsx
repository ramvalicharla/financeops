"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { FindingsTable } from "@/components/advisory/fdd/FindingsTable"
import { getFDDEngagement, runFDDEngagement } from "@/lib/api/fdd"
import type { FDDFinding, FDDEngagement, FDDSection } from "@/lib/types/fdd"

export default function FDDEngagementDetailPage() {
  const params = useParams()
  const engagementId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [engagement, setEngagement] = useState<FDDEngagement | null>(null)
  const [sections, setSections] = useState<FDDSection[]>([])
  const [findings, setFindings] = useState<FDDFinding[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    if (!engagementId) return
    try {
      const payload = await getFDDEngagement(engagementId)
      setEngagement(payload.engagement)
      setSections(payload.sections)
      setFindings(payload.findings)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load engagement")
    }
  }

  useEffect(() => {
    void load()
  }, [engagementId])

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      informational: 0,
    }
    for (const finding of findings) {
      counts[finding.severity] = (counts[finding.severity] ?? 0) + 1
    }
    return counts
  }, [findings])

  const runAnalysis = async () => {
    setRunning(true)
    setError(null)
    try {
      await runFDDEngagement(engagementId)
      await load()
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Failed to run analysis")
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{engagement?.engagement_name ?? "FDD Engagement"}</h1>
          <p className="text-sm text-muted-foreground">{engagement?.target_company_name ?? ""}</p>
        </div>
        <div className="flex items-center gap-2">
          {engagement?.status === "draft" ? (
            <button
              type="button"
              onClick={runAnalysis}
              disabled={running}
              className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
            >
              {running ? "Running..." : "Run Analysis"}
            </button>
          ) : null}
          <Link href={`/advisory/fdd/${engagementId}/report`} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            View Report
          </Link>
        </div>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Section Progress</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {engagement?.sections_requested.map((section) => {
            const done = sections.some((row) => row.section_name === section && row.status === "completed")
            const failed = sections.some((row) => row.section_name === section && row.status === "failed")
            return (
              <div key={section} className="rounded-md border border-border/60 bg-background px-3 py-2 text-sm">
                <p className="capitalize text-foreground">{section.replaceAll("_", " ")}</p>
                <p className="text-xs text-muted-foreground">
                  {done ? "completed" : failed ? "failed" : "pending"}
                </p>
              </div>
            )
          })}
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Critical</p>
          <p className="mt-1 text-2xl font-semibold text-[hsl(var(--brand-danger))]">{severityCounts.critical}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">High</p>
          <p className="mt-1 text-2xl font-semibold text-orange-300">{severityCounts.high}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Medium</p>
          <p className="mt-1 text-2xl font-semibold text-amber-300">{severityCounts.medium}</p>
        </div>
      </section>

      <FindingsTable findings={findings} />
    </div>
  )
}
