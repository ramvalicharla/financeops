"use client"

import Link from "next/link"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJournals } from "@/lib/api/accounting-journals"
import { getAccountingCashFlow } from "@/lib/api/accounting-statements"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const today = new Date().toISOString().slice(0, 10)
const monthStart = `${today.slice(0, 8)}01`

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function AccountingCashFlowPage() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [fromDate, setFromDate] = useState(monthStart)
  const [toDate, setToDate] = useState(today)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  const cashFlowQuery = useQuery({
    queryKey: ["accounting-cash-flow", activeEntityId, fromDate, toDate],
    enabled: Boolean(activeEntityId && fromDate && toDate),
    queryFn: async () =>
      getAccountingCashFlow({
        org_entity_id: activeEntityId as string,
        from_date: fromDate,
        to_date: toDate,
      }),
  })
  const journalsQuery = useQuery({
    queryKey: ["accounting-journals-cash-flow", activeEntityId, fromDate, toDate],
    enabled: Boolean(activeEntityId),
    queryFn: async () =>
      listJournals({
        org_entity_id: activeEntityId as string,
        status: "PUSHED",
        limit: 200,
      }),
  })

  const periodJournals = (journalsQuery.data ?? []).filter(
    (journal) => journal.journal_date >= fromDate && journal.journal_date <= toDate,
  )

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Cash Flow</h1>
          <p className="text-sm text-muted-foreground">
            Indirect cash flow built from GL balances and movement classifications.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/pnl">
            <Button variant="outline">P&L</Button>
          </Link>
          <Link href="/accounting/balance-sheet">
            <Button variant="outline">Balance Sheet</Button>
          </Link>
        </div>
      </header>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">From date</span>
          <input
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">To date</span>
          <input
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          />
        </label>
        <div className="flex items-end">
          <Button
            variant="outline"
            onClick={() => void cashFlowQuery.refetch()}
            disabled={cashFlowQuery.isFetching || !activeEntityId}
          >
            Refresh
          </Button>
        </div>
      </section>

      {cashFlowQuery.error ? (
        <div className="rounded-md border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-300">
          {cashFlowQuery.error instanceof Error
            ? cashFlowQuery.error.message
            : "Failed to load cash flow."}
        </div>
      ) : null}

      {cashFlowQuery.data ? (
        <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
          <Metric label="Operating Cash Flow" value={cashFlowQuery.data.operating_cash_flow} />
          <Metric label="Investing Cash Flow" value={cashFlowQuery.data.investing_cash_flow} />
          <Metric label="Financing Cash Flow" value={cashFlowQuery.data.financing_cash_flow} />
          <Metric label="Net Profit" value={cashFlowQuery.data.net_profit} />
          <Metric label="Working Capital Changes" value={cashFlowQuery.data.working_capital_changes} />
          <Metric label="Net Cash Flow" value={cashFlowQuery.data.net_cash_flow} />
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <header className="border-b border-border px-4 py-3">
          <h2 className="text-base font-semibold text-foreground">Cash Flow Breakdown</h2>
        </header>
        {cashFlowQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : (cashFlowQuery.data?.breakdown.length ?? 0) === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">No cash flow rows available.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Category</th>
                  <th scope="col" className="px-4 py-2">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {cashFlowQuery.data?.breakdown.map((row) => (
                  <tr
                    key={row.category}
                    role="row"
                    tabIndex={0}
                    className="cursor-pointer hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                    onClick={() => setSelectedCategory(row.category)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        setSelectedCategory(row.category)
                      }
                    }}
                    aria-label={`View details for ${row.category}`}
                  >
                    <td className="px-4 py-2 text-foreground">{row.category}</td>
                    <td className="px-4 py-2 text-foreground">{fmt(row.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-base font-semibold text-foreground">Related Journals</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          {selectedCategory
            ? `Posted journals in selected period for ${selectedCategory}`
            : "Select a cash-flow row to drill down to posted journals in-period."}
        </p>
        {!selectedCategory ? null : periodJournals.length === 0 ? (
          <p className="text-sm text-muted-foreground">No posted journals found in this period.</p>
        ) : (
          <div className="space-y-2">
            {periodJournals.map((journal) => (
              <div key={journal.id} className="rounded-md border border-border/70 p-3">
                <p className="text-sm font-medium text-foreground">
                  {journal.journal_number} - {journal.journal_date}
                </p>
                <p className="text-xs text-muted-foreground">{journal.reference ?? "No reference"}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/70 bg-background/50 p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{fmt(value)}</p>
    </div>
  )
}
