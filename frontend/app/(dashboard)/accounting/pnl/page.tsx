"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJournals } from "@/lib/api/accounting-journals"
import { getAccountingPnL } from "@/lib/api/accounting-statements"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const today = new Date().toISOString().slice(0, 10)
const monthStart = `${today.slice(0, 8)}01`

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function AccountingPnLPage() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [fromDate, setFromDate] = useState(monthStart)
  const [toDate, setToDate] = useState(today)
  const [selectedAccountCode, setSelectedAccountCode] = useState<string | null>(null)

  const pnlQuery = useQuery({
    queryKey: ["accounting-pnl", activeEntityId, fromDate, toDate],
    enabled: Boolean(activeEntityId && fromDate && toDate),
    queryFn: async () =>
      getAccountingPnL({
        org_entity_id: activeEntityId as string,
        from_date: fromDate,
        to_date: toDate,
      }),
  })

  const journalsQuery = useQuery({
    queryKey: ["accounting-journals-pnl", activeEntityId],
    enabled: Boolean(activeEntityId),
    queryFn: async () =>
      listJournals({
        org_entity_id: activeEntityId as string,
        status: "POSTED",
        limit: 200,
      }),
  })

  const accountJournals = useMemo(() => {
    if (!selectedAccountCode) return []
    const journals = journalsQuery.data ?? []
    return journals.filter((journal) =>
      journal.lines.some((line) => line.account_code === selectedAccountCode),
    )
  }, [journalsQuery.data, selectedAccountCode])

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Profit & Loss</h1>
          <p className="text-sm text-muted-foreground">
            Income statement derived from GL entries and CoA classifications.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/balance-sheet">
            <Button variant="outline">Balance Sheet</Button>
          </Link>
          <Link href="/accounting/cash-flow">
            <Button variant="outline">Cash Flow</Button>
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
            onClick={() => void pnlQuery.refetch()}
            disabled={pnlQuery.isFetching || !activeEntityId}
          >
            Refresh
          </Button>
        </div>
      </section>

      {pnlQuery.data ? (
        <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
          <Metric label="Revenue" value={pnlQuery.data.revenue} />
          <Metric label="Cost of Sales" value={pnlQuery.data.cost_of_sales} />
          <Metric label="Gross Profit" value={pnlQuery.data.gross_profit} />
          <Metric label="Operating Expense" value={pnlQuery.data.operating_expense} />
          <Metric label="Operating Profit" value={pnlQuery.data.operating_profit} />
          <Metric label="Net Profit" value={pnlQuery.data.net_profit} />
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {pnlQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : pnlQuery.error ? (
          <div className="p-4 text-sm text-rose-300">
            {pnlQuery.error instanceof Error ? pnlQuery.error.message : "Failed to load P&L."}
          </div>
        ) : (pnlQuery.data?.breakdown.length ?? 0) === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">No P&L breakdown rows available.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Category</th>
                  <th scope="col" className="px-4 py-2">Account</th>
                  <th scope="col" className="px-4 py-2">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {pnlQuery.data?.breakdown.map((row) => (
                  <tr
                    key={`${row.category}-${row.account_code}`}
                    role="row"
                    tabIndex={0}
                    className="cursor-pointer hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                    onClick={() => setSelectedAccountCode(row.account_code)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        setSelectedAccountCode(row.account_code)
                      }
                    }}
                    aria-label={`View details for ${row.account_name || row.account_code}`}
                  >
                    <td className="px-4 py-2 text-muted-foreground">{row.category}</td>
                    <td className="px-4 py-2">
                      <p className="font-medium text-foreground">{row.account_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{row.account_code}</p>
                    </td>
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
          {selectedAccountCode
            ? `Posted journals containing account ${selectedAccountCode}`
            : "Select an account row to inspect supporting journals."}
        </p>
        {!selectedAccountCode ? null : accountJournals.length === 0 ? (
          <p className="text-sm text-muted-foreground">No posted journals found for this account.</p>
        ) : (
          <div className="space-y-2">
            {accountJournals.map((journal) => (
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
