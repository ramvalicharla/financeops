"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  getPrepaidAmortisationSchedule,
  getPrepaidSchedule,
  listPrepaidEntries,
} from "@/lib/api/prepaid"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { queryKeys } from "@/lib/query/keys"

interface PrepaidDetailPageProps {
  params: {
    id: string
  }
}

export default function PrepaidDetailPage({ params }: PrepaidDetailPageProps) {
  const { fmt } = useFormattedAmount()

  const scheduleQuery = useQuery({
    queryKey: queryKeys.prepaid.schedule(params.id),
    queryFn: () => getPrepaidSchedule(params.id),
  })

  const amortisationQuery = useQuery({
    queryKey: queryKeys.prepaid.amortisation(params.id),
    queryFn: () => getPrepaidAmortisationSchedule(params.id),
  })

  const entriesQuery = useQuery({
    queryKey: queryKeys.prepaid.entries(params.id),
    queryFn: () => listPrepaidEntries(params.id, 0, 50),
  })

  const progressPct = useMemo(() => {
    if (!scheduleQuery.data) {
      return 0
    }
    const total = Number(scheduleQuery.data.total_amount)
    const amortised = Number(scheduleQuery.data.amortised_amount)
    if (!Number.isFinite(total) || total <= 0) {
      return 0
    }
    return Math.max(0, Math.min(100, (amortised / total) * 100))
  }, [scheduleQuery.data])

  if (scheduleQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        {Array.from({ length: 5 }).map((_, idx) => (
          <div key={idx} className="h-12 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    )
  }

  if (scheduleQuery.error || !scheduleQuery.data) {
    return <div className="p-6 text-sm text-[hsl(var(--brand-danger))]">Failed to load prepaid schedule.</div>
  }

  const schedule = scheduleQuery.data

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{schedule.description}</h1>
          <p className="font-mono text-xs text-muted-foreground">{schedule.reference_number}</p>
        </div>
        <span className="rounded-full bg-accent px-3 py-1 text-xs text-accent-foreground">{schedule.status}</span>
      </header>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Total</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(schedule.total_amount)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Amortised</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(schedule.amortised_amount)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Remaining</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(schedule.remaining_amount)}</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Amortisation progress</span>
          <span className="text-foreground">{progressPct.toFixed(2)}%</span>
        </div>
        <div className="mt-2 h-3 overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-[hsl(var(--brand-primary))]" style={{ width: `${progressPct}%` }} />
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium text-foreground">Amortisation Schedule</h2>
        </div>
        {amortisationQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, idx) => (
              <div key={idx} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label="Prepaid transactions" className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Period</th>
                  <th scope="col" className="px-4 py-2">Amount</th>
                  <th scope="col" className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(amortisationQuery.data ?? []).map((line) => (
                  <tr key={`${line.period_start}-${line.period_end}`}>
                    <td className="px-4 py-2">
                      {line.period_start} to {line.period_end}
                    </td>
                    <td className="px-4 py-2">{fmt(line.amount)}</td>
                    <td className="px-4 py-2">
                      <span
                        className={line.is_actual ? "text-foreground" : "text-muted-foreground"}
                      >
                        {line.is_actual ? "Actual" : "Projected"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium text-foreground">Actual Entries</h2>
        </div>
        <div className="overflow-x-auto">
          <table aria-label="Prepaid transactions" className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="px-4 py-2">Period</th>
                <th scope="col" className="px-4 py-2">Amount</th>
                <th scope="col" className="px-4 py-2">Run Reference</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(entriesQuery.data?.items ?? []).map((entry) => (
                <tr key={entry.id}>
                  <td className="px-4 py-2">
                    {entry.period_start} to {entry.period_end}
                  </td>
                  <td className="px-4 py-2">{fmt(entry.amortisation_amount)}</td>
                  <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{entry.run_reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
