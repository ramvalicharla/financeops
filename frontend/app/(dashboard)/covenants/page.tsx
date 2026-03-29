"use client"

import { useEffect, useState } from "react"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"
import { CovenantCard } from "@/components/covenants/CovenantCard"
import { getCovenantDashboard, runCovenantCheck } from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import { type CovenantDashboard } from "@/lib/types/sprint11"

const currentPeriod = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`

export default function CovenantsPage() {
  const [dashboard, setDashboard] = useState<CovenantDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [runningCheck, setRunningCheck] = useState(false)

  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getCovenantDashboard()
      setDashboard(payload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load covenant dashboard")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const runCheck = async (): Promise<void> => {
    setRunningCheck(true)
    setError(null)
    try {
      await runCovenantCheck(currentPeriod)
      await load()
    } catch (checkError) {
      setError(checkError instanceof Error ? checkError.message : "Failed to run covenant check")
    } finally {
      setRunningCheck(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Debt Covenants</h1>
        <div className="flex items-center gap-2">
          <ScaleSelector value={scale} onChange={setScale} />
          <Button variant="outline" onClick={() => void runCheck()} disabled={runningCheck}>
            {runningCheck ? "Running..." : "Run Covenant Check"}
          </Button>
        </div>
      </div>

      {dashboard ? (
        <section className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl border border-green-500/40 bg-green-500/10 p-3 text-sm text-green-300">
            Passing: {dashboard.passing}
          </div>
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
            Near Breach: {dashboard.near_breach}
          </div>
          <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            Breached: {dashboard.breached}
          </div>
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            Total: {dashboard.total_covenants}
          </div>
        </section>
      ) : null}

      {loading ? <p className="text-sm text-muted-foreground">Loading covenants...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {dashboard?.covenants.map((item) => (
          <CovenantCard
            key={item.definition.id}
            facilityName={item.definition.facility_name}
            covenantLabel={item.definition.covenant_label}
            covenantType={item.definition.covenant_type}
            threshold={item.definition.threshold_value}
            actual={item.latest_event?.actual_value ?? "0"}
            direction={item.definition.threshold_direction}
            status={item.latest_event?.breach_type ?? "pass"}
            headroomPct={item.headroom_pct}
            trend={item.trend}
          />
        ))}
      </div>
    </div>
  )
}
