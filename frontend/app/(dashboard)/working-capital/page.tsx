"use client"

import dynamic from "next/dynamic"
import { useEffect, useMemo, useState } from "react"
import { APAgingTable } from "@/components/working-capital/APAgingTable"
import { ARAgingTable } from "@/components/working-capital/ARAgingTable"
import { CashCycleChart } from "@/components/working-capital/CashCycleChart"
import { WCKPICard } from "@/components/working-capital/WCKPICard"
import { fetchWCDashboard } from "@/lib/api/working-capital"
import type { WCDashboardPayload } from "@/lib/types/working-capital"
import { decimalStringToNumber } from "@/lib/utils"

const WorkingCapitalChart = dynamic(
  () =>
    import("@/components/charts/WorkingCapitalChart").then(
      (module) => module.WorkingCapitalChart,
    ),
  {
    ssr: false,
    loading: () => <div className="h-64 w-full animate-pulse rounded-lg bg-muted" />,
  },
)

export default function WorkingCapitalPage() {
  const [payload, setPayload] = useState<WCDashboardPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        setPayload(await fetchWCDashboard())
      } catch (fetchError) {
        setError(
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load working capital",
        )
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  const arBars = useMemo(() => {
    if (!payload) return []
    const snapshot = payload.current_snapshot
    return [
      { bucket: "Current", value: decimalStringToNumber(snapshot.ar_current) },
      { bucket: "31-60", value: decimalStringToNumber(snapshot.ar_30) },
      { bucket: "61-90", value: decimalStringToNumber(snapshot.ar_60) },
      { bucket: "90+", value: decimalStringToNumber(snapshot.ar_90) },
    ]
  }, [payload])

  const apBars = useMemo(() => {
    if (!payload) return []
    const snapshot = payload.current_snapshot
    return [
      { bucket: "Current", value: decimalStringToNumber(snapshot.ap_current) },
      { bucket: "31-60", value: decimalStringToNumber(snapshot.ap_30) },
      { bucket: "61-90", value: decimalStringToNumber(snapshot.ap_60) },
      { bucket: "90+", value: decimalStringToNumber(snapshot.ap_90) },
    ]
  }, [payload])

  if (loading) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />
  }

  if (!payload || error) {
    return (
      <p className="rounded-md border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.15)] px-4 py-3 text-sm text-[hsl(var(--brand-danger))]">
        {error ?? "Unable to load dashboard"}
      </p>
    )
  }

  const snapshot = payload.current_snapshot

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <WCKPICard
          label="DSO"
          value={snapshot.dso_days}
          unit="days"
          change={payload.mom_changes.dso}
          change_direction={
            decimalStringToNumber(payload.mom_changes.dso) >= 0 ? "up" : "down"
          }
          is_good={false}
        />
        <WCKPICard
          label="DPO"
          value={snapshot.dpo_days}
          unit="days"
          change={payload.mom_changes.dpo}
          change_direction={
            decimalStringToNumber(payload.mom_changes.dpo) >= 0 ? "up" : "down"
          }
          is_good={true}
        />
        <WCKPICard
          label="CCC"
          value={snapshot.ccc_days}
          unit="days"
          change={payload.mom_changes.ccc}
          change_direction={
            decimalStringToNumber(payload.mom_changes.ccc) >= 0 ? "up" : "down"
          }
          is_good={false}
        />
        <WCKPICard
          label="Net WC"
          value={snapshot.net_working_capital}
          unit="₹"
          change={payload.mom_changes.nwc}
          change_direction={
            decimalStringToNumber(payload.mom_changes.nwc) >= 0 ? "up" : "down"
          }
          is_good={true}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <WorkingCapitalChart title="AR Aging" data={arBars} barColor="#60A5FA" />
        <WorkingCapitalChart title="AP Aging" data={apBars} barColor="#F59E0B" />
      </section>

      <CashCycleChart trends={payload.trends} />

      <section className="grid gap-4 lg:grid-cols-2">
        <ARAgingTable rows={payload.top_overdue_ar} />
        <APAgingTable rows={payload.discount_opportunities} />
      </section>
    </div>
  )
}
