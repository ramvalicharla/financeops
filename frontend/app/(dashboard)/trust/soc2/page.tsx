"use client"

import { useEffect, useMemo, useState } from "react"
import { getSoc2Dashboard, getSoc2Evidence, listSoc2Controls } from "@/lib/api/compliance"
import type { ComplianceControl, ComplianceDashboard } from "@/lib/types/compliance"
import { ComplianceProgress } from "@/components/compliance/ComplianceProgress"
import { ControlCard } from "@/components/compliance/ControlCard"
import { EvidencePanel } from "@/components/compliance/EvidencePanel"

export default function TrustSoc2Page() {
  const [dashboard, setDashboard] = useState<ComplianceDashboard | null>(null)
  const [controls, setControls] = useState<ComplianceControl[]>([])
  const [selected, setSelected] = useState<ComplianceControl | null>(null)

  useEffect(() => {
    const load = async () => {
      const [dashboardData, controlsData] = await Promise.all([
        getSoc2Dashboard(),
        listSoc2Controls({ limit: 200, offset: 0 }),
      ])
      setDashboard(dashboardData)
      setControls(controlsData.data)
    }
    void load()
  }, [])

  const grouped = useMemo(() => {
    const map = new Map<string, ComplianceControl[]>()
    for (const control of controls) {
      const bucket = map.get(control.category) ?? []
      bucket.push(control)
      map.set(control.category, bucket)
    }
    return Array.from(map.entries())
  }, [controls])

  const downloadEvidence = async () => {
    const payload = await getSoc2Evidence()
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "soc2_trust_evidence.json"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">SOC2 Type II Compliance</h1>
          <p className="text-sm text-muted-foreground">
            This platform undergoes continuous SOC2 monitoring. Below is the current control status for your reference.
          </p>
        </div>
        <button type="button" onClick={() => void downloadEvidence()} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Download Evidence Package
        </button>
      </header>

      {dashboard ? <ComplianceProgress summary={dashboard.summary} /> : null}

      <section className="space-y-4">
        {grouped.map(([category, rows]) => (
          <div key={category} className="space-y-2">
            <h2 className="text-sm uppercase tracking-[0.16em] text-muted-foreground">{category}</h2>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {rows.map((control) => (
                <ControlCard key={control.control_id} control={control} isAdminView={false} onSelect={setSelected} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <EvidencePanel
        framework="soc2"
        control={selected}
        open={selected !== null}
        isAdminView={false}
        onClose={() => setSelected(null)}
      />
    </div>
  )
}

