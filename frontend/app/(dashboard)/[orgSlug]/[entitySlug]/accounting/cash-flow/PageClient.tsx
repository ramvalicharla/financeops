"use client"

import { useCallback, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { getAccountingCashFlow, type CashFlowResult } from "@/lib/api/accounting-statements"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatINR } from "@/lib/utils"

const FlowCard = ({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" }) => {
  const color = tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-foreground"
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${color}`}>{value}</p>
    </div>
  )
}

export default function CashFlowPage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const today = new Date().toISOString().slice(0, 10)
  const firstOfYear = `${new Date().getFullYear()}-01-01`
  const [fromDate, setFromDate] = useState(firstOfYear)
  const [toDate, setToDate] = useState(today)

  const query = useQuery<CashFlowResult>({
    queryKey: queryKeys.accounting.cashFlow(entityId, fromDate, toDate),
    queryFn: () => getAccountingCashFlow({ org_entity_id: entityId!, from_date: fromDate, to_date: toDate }),
    enabled: Boolean(entityId) && Boolean(fromDate) && Boolean(toDate),
  })

  const fmt = useCallback((v: string | undefined) => formatINR(v ?? "0"), [])

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Cash Flow Statement</h1>
          <p className="text-sm text-muted-foreground">Operating, investing, and financing activities for the period.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground" />
          <span className="text-sm text-muted-foreground">to</span>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground" />
          <Button variant="outline" size="sm" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? "Loading…" : "Refresh"}
          </Button>
        </div>
      </header>

      {query.isError && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {query.error instanceof Error ? query.error.message : "Failed to load cash flow statement."}
        </p>
      )}

      {query.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : query.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FlowCard label="Net Profit" value={fmt(query.data.net_profit)} />
            <FlowCard label="Non-Cash Adjustments" value={fmt(query.data.non_cash_adjustments)} />
            <FlowCard label="Working Capital Changes" value={fmt(query.data.working_capital_changes)} />
            <FlowCard label="Operating Cash Flow" value={fmt(query.data.operating_cash_flow)}
              tone={parseFloat(query.data.operating_cash_flow) >= 0 ? "positive" : "negative"} />
            <FlowCard label="Investing Cash Flow" value={fmt(query.data.investing_cash_flow)}
              tone={parseFloat(query.data.investing_cash_flow) >= 0 ? "positive" : "negative"} />
            <FlowCard label="Financing Cash Flow" value={fmt(query.data.financing_cash_flow)}
              tone={parseFloat(query.data.financing_cash_flow) >= 0 ? "positive" : "negative"} />
          </div>

          <div className="rounded-xl border border-border bg-card px-4 py-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">Net Cash Flow</p>
            <span className={`text-lg font-bold tabular-nums ${parseFloat(query.data.net_cash_flow) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {fmt(query.data.net_cash_flow)}
            </span>
          </div>

          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Detailed Breakdown</h2>
            </div>
            <div className="divide-y divide-border">
              {query.data.breakdown.map((row, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-3">
                  <p className="text-sm text-muted-foreground">{row.category}</p>
                  <span className="text-sm tabular-nums font-medium text-foreground">{fmt(row.amount)}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Select a date range to generate the cash flow statement.</p>
      )}
    </div>
  )
}
