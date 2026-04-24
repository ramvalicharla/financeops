"use client"

import { useCallback, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import { useTenantStore } from "@/lib/store/tenant"
import { getAccountingBalanceSheet, type BalanceSheetResult } from "@/lib/api/accounting-statements"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatINR } from "@/lib/utils"

export default function BalanceSheetPage() {
  const params = useParams<{ orgSlug: string; entitySlug: string }>()
  const activeEntityId = useTenantStore((s) => s.active_entity_id)
  const [asOfDate, setAsOfDate] = useState(() => new Date().toISOString().slice(0, 10))

  const query = useQuery<BalanceSheetResult>({
    queryKey: queryKeys.accounting.balanceSheet(activeEntityId, asOfDate),
    queryFn: () => getAccountingBalanceSheet({ org_entity_id: activeEntityId!, as_of_date: asOfDate }),
    enabled: Boolean(activeEntityId) && Boolean(asOfDate),
  })

  const fmt = useCallback((v: string | undefined) => formatINR(v ?? "0"), [])

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Balance Sheet</h1>
          <p className="text-sm text-muted-foreground">Assets, liabilities and equity as of a given date.</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <Button variant="outline" size="sm" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? "Loading…" : "Refresh"}
          </Button>
        </div>
      </header>

      {query.isError && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {query.error instanceof Error ? query.error.message : "Failed to load balance sheet."}
        </p>
      )}

      {query.isLoading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      ) : query.data ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Assets */}
          <section className="rounded-xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Assets</h2>
              <span className="text-sm font-semibold text-foreground">{fmt(query.data.totals.assets)}</span>
            </div>
            <div className="divide-y divide-border">
              {query.data.assets.map((item) => (
                <div key={item.account_code} className="flex items-center justify-between px-4 py-2">
                  <div>
                    <p className="text-sm text-foreground">{item.account_name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{item.account_code} · {item.account_type}</p>
                  </div>
                  <span className="text-sm tabular-nums text-foreground">{fmt(item.amount)}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Liabilities + Equity */}
          <div className="space-y-6">
            <section className="rounded-xl border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <h2 className="text-sm font-semibold text-foreground">Liabilities</h2>
                <span className="text-sm font-semibold text-foreground">{fmt(query.data.totals.liabilities)}</span>
              </div>
              <div className="divide-y divide-border">
                {query.data.liabilities.map((item) => (
                  <div key={item.account_code} className="flex items-center justify-between px-4 py-2">
                    <div>
                      <p className="text-sm text-foreground">{item.account_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{item.account_code}</p>
                    </div>
                    <span className="text-sm tabular-nums text-foreground">{fmt(item.amount)}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <h2 className="text-sm font-semibold text-foreground">Equity</h2>
                <span className="text-sm font-semibold text-foreground">{fmt(query.data.totals.equity)}</span>
              </div>
              <div className="divide-y divide-border">
                {query.data.equity.map((item) => (
                  <div key={item.account_code} className="flex items-center justify-between px-4 py-2">
                    <div>
                      <p className="text-sm text-foreground">{item.account_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{item.account_code}</p>
                    </div>
                    <span className="text-sm tabular-nums text-foreground">{fmt(item.amount)}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between px-4 py-2">
                  <p className="text-sm text-muted-foreground">Retained Earnings</p>
                  <span className="text-sm tabular-nums text-foreground">{fmt(query.data.retained_earnings)}</span>
                </div>
              </div>
            </section>

            <div className="rounded-xl border border-border bg-card px-4 py-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Total Liabilities & Equity</p>
              <span className="text-sm font-semibold text-foreground">{fmt(query.data.totals.liabilities_and_equity)}</span>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Select a date to load the balance sheet.</p>
      )}
    </div>
  )
}
