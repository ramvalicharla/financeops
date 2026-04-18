"use client"

import { useCallback, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useTenantStore } from "@/lib/store/tenant"
import { getAccountingPnL, type PnLResult } from "@/lib/api/accounting-statements"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatINR } from "@/lib/utils"

const KPICard = ({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" | "neutral" }) => {
  const color = tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-foreground"
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${color}`}>{value}</p>
    </div>
  )
}

export default function PnLPage() {
  const activeEntityId = useTenantStore((s) => s.active_entity_id)
  const today = new Date().toISOString().slice(0, 10)
  const firstOfYear = `${new Date().getFullYear()}-01-01`
  const [fromDate, setFromDate] = useState(firstOfYear)
  const [toDate, setToDate] = useState(today)

  const query = useQuery<PnLResult>({
    queryKey: ["pnl", activeEntityId, fromDate, toDate],
    queryFn: () => getAccountingPnL({ org_entity_id: activeEntityId!, from_date: fromDate, to_date: toDate }),
    enabled: Boolean(activeEntityId) && Boolean(fromDate) && Boolean(toDate),
  })

  const fmt = useCallback((v: string | undefined) => formatINR(v ?? "0"), [])

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Profit & Loss</h1>
          <p className="text-sm text-muted-foreground">Income statement for the selected period.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground" />
          <span className="text-muted-foreground text-sm">to</span>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground" />
          <Button variant="outline" size="sm" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? "Loading…" : "Refresh"}
          </Button>
        </div>
      </header>

      {query.isError && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {query.error instanceof Error ? query.error.message : "Failed to load P&L."}
        </p>
      )}

      {query.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      ) : query.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KPICard label="Revenue" value={fmt(query.data.revenue)} tone="positive" />
            <KPICard label="Cost of Sales" value={fmt(query.data.cost_of_sales)} tone="negative" />
            <KPICard label="Gross Profit" value={fmt(query.data.gross_profit)} tone="positive" />
            <KPICard label="Operating Expenses" value={fmt(query.data.operating_expense)} tone="negative" />
            <KPICard label="Operating Profit" value={fmt(query.data.operating_profit)}
              tone={parseFloat(query.data.operating_profit) >= 0 ? "positive" : "negative"} />
            <KPICard label="Other Income" value={fmt(query.data.other_income)} tone="positive" />
            <KPICard label="Other Expense" value={fmt(query.data.other_expense)} tone="negative" />
            <KPICard label="Net Profit" value={fmt(query.data.net_profit)}
              tone={parseFloat(query.data.net_profit) >= 0 ? "positive" : "negative"} />
          </div>

          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Breakdown by Account</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2">Category</th>
                    <th className="px-4 py-2">Account</th>
                    <th className="px-4 py-2 text-right">Debit</th>
                    <th className="px-4 py-2 text-right">Credit</th>
                    <th className="px-4 py-2 text-right">Net</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {query.data.breakdown.map((row, i) => (
                    <tr key={`${row.account_code}-${i}`} className="hover:bg-muted/20">
                      <td className="px-4 py-2 text-muted-foreground">{row.category}</td>
                      <td className="px-4 py-2">
                        <p className="font-medium text-foreground">{row.account_name}</p>
                        <p className="font-mono text-xs text-muted-foreground">{row.account_code}</p>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmt(row.debit_sum)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmt(row.credit_sum)}</td>
                      <td className="px-4 py-2 text-right tabular-nums font-medium">{fmt(row.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Select a date range to generate the P&L statement.</p>
      )}
    </div>
  )
}
