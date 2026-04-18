"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  evaluateSoc2,
  getSoc2Dashboard,
  getSoc2Evidence,
  listSoc2Controls,
  updateSoc2ControlStatus,
} from "@/lib/api/compliance"
import type { ComplianceControl, ComplianceDashboard } from "@/lib/types/compliance"
import { ComplianceProgress } from "@/components/compliance/ComplianceProgress"
import { ControlCard } from "@/components/compliance/ControlCard"
import { EvidencePanel } from "@/components/compliance/EvidencePanel"

const FILTERS = ["all", "green", "amber", "red", "grey", "auto"] as const

export default function AdminSoc2Page() {
  const [dashboard, setDashboard] = useState<ComplianceDashboard | null>(null)
  const [controls, setControls] = useState<ComplianceControl[]>([])
  const [selected, setSelected] = useState<ComplianceControl | null>(null)
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [dashboardData, controlsData] = await Promise.all([
        getSoc2Dashboard(),
        listSoc2Controls({ limit: 200, offset: 0 }),
      ])
      setDashboard(dashboardData)
      setControls(controlsData.data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load SOC2 controls")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const visible = useMemo(() => {
    if (filter === "all") return controls
    if (filter === "auto") return controls.filter((row) => row.auto_evaluable)
    return controls.filter((row) => row.rag_status === filter)
  }, [controls, filter])

  const grouped = useMemo(() => {
    const map = new Map<string, ComplianceControl[]>()
    for (const control of visible) {
      const bucket = map.get(control.category) ?? []
      bucket.push(control)
      map.set(control.category, bucket)
    }
    return Array.from(map.entries())
  }, [visible])

  const runAuto = async () => {
    setError(null)
    try {
      const result = await evaluateSoc2()
      setMessage(`${result.passed} passed, ${result.failed} failed`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to run SOC2 auto-evaluation")
    }
  }

  const downloadEvidence = async () => {
    const payload = await getSoc2Evidence()
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "soc2_evidence_package.json"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-foreground">SOC2 Controls</h1>
        <div className="flex gap-2">
          <button type="button" onClick={() => void runAuto()} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            Run Auto-Evaluation
          </button>
          <button type="button" onClick={() => void downloadEvidence()} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            Export Evidence Package
          </button>
        </div>
      </header>

      {dashboard ? <ComplianceProgress summary={dashboard.summary} /> : null}
      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading SOC2 controls...</p> : null}

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((tag) => (
          <button
            key={tag}
            type="button"
            onClick={() => setFilter(tag)}
            className={`rounded-full border px-3 py-1 text-xs ${filter === tag ? "border-[hsl(var(--brand-primary))] text-foreground" : "border-border text-muted-foreground"}`}
          >
            {tag.toUpperCase()}
          </button>
        ))}
      </div>

      <section className="space-y-4">
        {grouped.length ? (
          grouped.map(([category, rows]) => (
            <div key={category} className="space-y-2">
              <h2 className="text-sm uppercase tracking-[0.16em] text-muted-foreground">{category}</h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {rows.map((control) => (
                  <ControlCard key={control.control_id} control={control} isAdminView onSelect={setSelected} />
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
            No SOC2 controls matched the current filter.
          </div>
        )}
      </section>

      <EvidencePanel
        framework="soc2"
        control={selected}
        open={selected !== null}
        isAdminView
        onClose={() => setSelected(null)}
        onUpdateStatus={async (controlId, status, notes) => {
          await updateSoc2ControlStatus(controlId, { status, notes })
          await load()
        }}
      />
    </div>
  )
}

