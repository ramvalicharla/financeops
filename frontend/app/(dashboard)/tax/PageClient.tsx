"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { DeferredTaxSchedule } from "@/components/tax/DeferredTaxSchedule"
import { TaxProvisionTable } from "@/components/tax/TaxProvisionTable"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { computeTaxProvision, getTaxSchedule } from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import { type TaxSchedule } from "@/lib/types/sprint11"

const currentYear = new Date().getFullYear()
const defaultPeriod = `${currentYear}-${String(new Date().getMonth() + 1).padStart(2, "0")}`

export default function TaxPage() {
  const [schedule, setSchedule] = useState<TaxSchedule | null>(null)
  const [period, setPeriod] = useState(defaultPeriod)
  const [rate, setRate] = useState("0.2517")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { fmt, fmtPct } = useFormattedAmount()
  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getTaxSchedule(currentYear)
      setSchedule(payload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load tax schedule")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const currentProvision = useMemo(() => {
    if (!schedule || schedule.periods.length === 0) {
      return null
    }
    return schedule.periods.find((row) => row.period === period) ?? schedule.periods[0]
  }, [period, schedule])

  const runCompute = async (): Promise<void> => {
    setError(null)
    try {
      await computeTaxProvision({
        period,
        applicable_tax_rate: rate,
        tax_rate_description: "Manual from UI",
      })
      await load()
    } catch (computeError) {
      setError(computeError instanceof Error ? computeError.message : "Provision compute failed")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Tax Provision</h1>
          <p className="text-sm text-muted-foreground">
            Annual tax summary and deferred tax position tracking.
          </p>
        </div>
        <ScaleSelector value={scale} onChange={setScale} />
      </div>

      <section className="grid gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">YTD Current Tax</p>
          <p className="text-lg font-semibold text-foreground">
            {schedule ? fmt(schedule.ytd_current_tax) : "-"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">YTD Deferred Tax</p>
          <p className="text-lg font-semibold text-foreground">
            {schedule ? fmt(schedule.ytd_deferred_tax) : "-"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">YTD Total Tax</p>
          <p className="text-lg font-semibold text-foreground">
            {schedule ? fmt(schedule.ytd_total_tax) : "-"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Effective Tax Rate</p>
          <p className="text-lg font-semibold text-foreground">
            {schedule ? fmtPct(schedule.effective_tax_rate_ytd) : "-"}
          </p>
          <p className="text-xs text-muted-foreground">Statutory: 25.17%</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-2 md:grid-cols-4">
          <FormField id="tax-period" label="Period"><Input value={period} onChange={(event) => setPeriod(event.target.value)} /></FormField>
          <FormField id="tax-rate" label="Applicable tax rate"><Input value={rate} onChange={(event) => setRate(event.target.value)} inputMode="decimal" /></FormField>
          <Button variant="outline" onClick={() => void runCompute()}>
            Compute Provision
          </Button>
          {currentProvision ? (
            <Link
              href={`/tax/${currentProvision.period}`}
              className="inline-flex items-center justify-center rounded-md border border-border px-3 py-2 text-sm text-foreground"
            >
              Open Period Detail
            </Link>
          ) : null}
        </div>
      </section>

      {loading ? <p className="text-sm text-muted-foreground">Loading tax schedule...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {currentProvision ? <TaxProvisionTable provision={currentProvision} /> : null}
      {schedule ? (
        <DeferredTaxSchedule positions={schedule.deferred_tax_positions} />
      ) : null}
    </div>
  )
}
