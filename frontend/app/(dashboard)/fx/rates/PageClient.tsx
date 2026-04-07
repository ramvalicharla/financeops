"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { createFxRate, listFxRates, type FxRateType } from "@/lib/api/fx-rates"

const TODAY = new Date().toISOString().slice(0, 10)

export default function FxRatesPage() {
  const queryClient = useQueryClient()
  const [fromCurrency, setFromCurrency] = useState("USD")
  const [toCurrency, setToCurrency] = useState("INR")
  const [rateType, setRateType] = useState<FxRateType>("SPOT")
  const [effectiveDate, setEffectiveDate] = useState(TODAY)
  const [rate, setRate] = useState("")
  const [source, setSource] = useState("manual")
  const [error, setError] = useState<string | null>(null)

  const ratesQuery = useQuery({
    queryKey: ["fx-rates"],
    queryFn: async () => listFxRates({ limit: 200 }),
  })

  const createMutation = useMutation({
    mutationFn: createFxRate,
    onSuccess: async () => {
      setRate("")
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ["fx-rates"] })
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Failed to create FX rate")
    },
  })

  const sortedRates = useMemo(
    () =>
      [...(ratesQuery.data?.rates ?? [])].sort((a, b) =>
        `${b.effective_date}${b.created_at}`.localeCompare(`${a.effective_date}${a.created_at}`),
      ),
    [ratesQuery.data?.rates],
  )

  const submitRate = async () => {
    setError(null)
    if (!rate.trim()) {
      setError("Rate is required.")
      return
    }
    await createMutation.mutateAsync({
      from_currency: fromCurrency.toUpperCase(),
      to_currency: toCurrency.toUpperCase(),
      rate,
      rate_type: rateType,
      effective_date: effectiveDate,
      source,
      is_global: false,
    })
  }

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-2xl font-semibold text-foreground">FX Rate Master</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Maintain IAS 21 rates by type (spot, average, closing).
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground">Add Rate</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-6">
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={fromCurrency}
            onChange={(event) => setFromCurrency(event.target.value)}
            placeholder="From (USD)"
          />
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={toCurrency}
            onChange={(event) => setToCurrency(event.target.value)}
            placeholder="To (INR)"
          />
          <select
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={rateType}
            onChange={(event) => setRateType(event.target.value as FxRateType)}
          >
            <option value="SPOT">SPOT</option>
            <option value="AVERAGE">AVERAGE</option>
            <option value="CLOSING">CLOSING</option>
          </select>
          <input
            type="date"
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={effectiveDate}
            onChange={(event) => setEffectiveDate(event.target.value)}
          />
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={rate}
            onChange={(event) => setRate(event.target.value)}
            placeholder="Rate"
          />
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            placeholder="Source"
          />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button
            type="button"
            disabled={createMutation.isPending}
            onClick={() => void submitRate()}
          >
            {createMutation.isPending ? "Saving..." : "Save Rate"}
          </Button>
          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : null}
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-lg font-semibold text-foreground">Rates</h2>
          <Button
            type="button"
            variant="outline"
            onClick={() => void ratesQuery.refetch()}
            disabled={ratesQuery.isFetching}
          >
            {ratesQuery.isFetching ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Pair</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2 text-right">Rate</th>
                <th className="px-4 py-2">Effective Date</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Scope</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sortedRates.map((row) => (
                <tr key={row.id}>
                  <td className="px-4 py-2">{row.from_currency}/{row.to_currency}</td>
                  <td className="px-4 py-2">{row.rate_type}</td>
                  <td className="px-4 py-2 text-right">{row.rate}</td>
                  <td className="px-4 py-2">{row.effective_date}</td>
                  <td className="px-4 py-2">{row.source}</td>
                  <td className="px-4 py-2">{row.tenant_id ? "TENANT" : "GLOBAL"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

