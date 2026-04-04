"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { CashPositionCard } from "@/components/treasury/CashPositionCard"
import {
  createTreasuryForecast,
  getTreasuryForecast,
  listTreasuryForecasts,
  publishTreasuryForecast,
} from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import { type ForecastRun, type ForecastSummary } from "@/lib/types/sprint11"

const todayIso = new Date().toISOString().slice(0, 10)

export default function TreasuryPage() {
  const [runs, setRuns] = useState<ForecastRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [publishedSummary, setPublishedSummary] = useState<ForecastSummary | null>(null)
  const [runName, setRunName] = useState("Weekly Treasury Run")
  const [baseDate, setBaseDate] = useState(todayIso)
  const [openingBalance, setOpeningBalance] = useState("1000000.00")
  const [creating, setCreating] = useState(false)

  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listTreasuryForecasts({ limit: 50, offset: 0 })
      setRuns(payload.data)
      const publishedRun = payload.data.find((row) => row.status === "published")
      if (publishedRun) {
        const summary = await getTreasuryForecast(publishedRun.id)
        setPublishedSummary(summary)
      } else {
        setPublishedSummary(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load forecasts")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const published = useMemo(
    () => runs.find((row) => row.status === "published") ?? null,
    [runs],
  )

  const createRun = async (): Promise<void> => {
    setCreating(true)
    setError(null)
    try {
      await createTreasuryForecast({
        run_name: runName,
        base_date: baseDate,
        opening_cash_balance: openingBalance,
        currency: "INR",
        weeks: 13,
        seed_historical: true,
      })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create forecast")
    } finally {
      setCreating(false)
    }
  }

  const publishRun = async (runId: string): Promise<void> => {
    try {
      await publishTreasuryForecast(runId)
      await load()
    } catch (publishError) {
      setError(publishError instanceof Error ? publishError.message : "Failed to publish forecast")
    }
  }

  return (
    <div className="space-y-6 p-2">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">13-Week Cash Flow Forecast</h1>
          <p className="text-sm text-muted-foreground">
            Rolling treasury forecast and liquidity risk monitoring.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ScaleSelector value={scale} onChange={setScale} />
          <Button type="button" variant="outline" onClick={() => void load()}>
            Refresh
          </Button>
        </div>
      </header>

      {published ? (
        <CashPositionCard
          opening={publishedSummary?.opening_balance ?? published.opening_cash_balance}
          minimum={publishedSummary?.minimum_balance ?? published.opening_cash_balance}
          minimumWeek={publishedSummary?.minimum_balance_week ?? 1}
          closing={publishedSummary?.closing_balance_week_13 ?? published.opening_cash_balance}
          isCashPositive={publishedSummary?.is_cash_positive ?? true}
        />
      ) : (
        <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
          No published forecast yet.
        </p>
      )}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">New 13-Week Forecast</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <FormField id="treasury-run-name" label="Forecast name"><Input value={runName} onChange={(event) => setRunName(event.target.value)} /></FormField>
          <FormField id="treasury-base-date" label="Base date"><Input type="date" value={baseDate} onChange={(event) => setBaseDate(event.target.value)} /></FormField>
          <FormField id="treasury-opening-balance" label="Opening balance"><Input
            value={openingBalance}
            onChange={(event) => setOpeningBalance(event.target.value)}
            inputMode="decimal"
          /></FormField>
        </div>
        <Button className="mt-3" type="button" onClick={() => void createRun()} disabled={creating}>
          {creating ? "Creating..." : "Create Forecast"}
        </Button>
      </section>

      {loading ? <p className="text-sm text-muted-foreground">Loading forecasts...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      <section className="space-y-2">
        {runs.map((run) => (
          <div
            key={run.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3"
          >
            <div>
              <p className="font-medium text-foreground">{run.run_name}</p>
              <p className="text-xs text-muted-foreground">
                {run.base_date} - {run.currency} - {run.status}
              </p>
            </div>
            <div className="flex gap-2">
              <Link
                href={`/treasury/${run.id}`}
                className="rounded-md border border-border px-3 py-1.5 text-xs text-foreground"
              >
                Open
              </Link>
              {run.status === "draft" ? (
                <Button size="sm" variant="outline" onClick={() => void publishRun(run.id)}>
                  Publish
                </Button>
              ) : null}
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
