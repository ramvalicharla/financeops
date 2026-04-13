"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getAccountingTrialBalance } from "@/lib/api/accounting-trial-balance"
import { listJournals } from "@/lib/api/accounting-journals"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const today = new Date().toISOString().slice(0, 10)

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function AccountingTrialBalancePage() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [asOfDate, setAsOfDate] = useState(today)
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [selectedAccountCode, setSelectedAccountCode] = useState<string | null>(null)

  const trialBalanceQuery = useQuery({
    queryKey: ["accounting-trial-balance", activeEntityId, asOfDate, fromDate, toDate],
    enabled: Boolean(activeEntityId && asOfDate),
    queryFn: async () =>
      getAccountingTrialBalance({
        org_entity_id: activeEntityId as string,
        as_of_date: asOfDate,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      }),
  })

  const journalsQuery = useQuery({
    queryKey: ["accounting-journals-for-tb", activeEntityId],
    enabled: Boolean(activeEntityId),
    queryFn: async () =>
      listJournals({
        org_entity_id: activeEntityId as string,
        status: "PUSHED",
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

  const rows = trialBalanceQuery.data?.rows ?? []

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Accounting Trial Balance</h1>
          <p className="text-sm text-muted-foreground">
            GL-derived trial balance with account-level drilldown to posted journals.
          </p>
        </div>
        <Link href="/accounting/journals">
          <Button variant="outline">Back to Journals</Button>
        </Link>
      </header>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">As of date</span>
          <input
            type="date"
            value={asOfDate}
            onChange={(event) => setAsOfDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          />
        </label>
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
            type="button"
            variant="outline"
            onClick={() => void trialBalanceQuery.refetch()}
            disabled={trialBalanceQuery.isFetching || !activeEntityId}
          >
            Refresh
          </Button>
        </div>
      </section>

      {trialBalanceQuery.error ? (
        <div className="rounded-md border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-300">
          {trialBalanceQuery.error instanceof Error
            ? trialBalanceQuery.error.message
            : "Failed to load trial balance."}
        </div>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {trialBalanceQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">
            No trial-balance rows found for selected filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Account</th>
                  <th scope="col" className="px-4 py-2">Debit</th>
                  <th scope="col" className="px-4 py-2">Credit</th>
                  <th scope="col" className="px-4 py-2">Balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row) => (
                  <tr
                    key={`${row.account_code}-${row.account_name}`}
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
                    <td className="px-4 py-2">
                      <p className="font-medium text-foreground">{row.account_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{row.account_code}</p>
                    </td>
                    <td className="px-4 py-2 text-foreground">{fmt(row.debit_sum)}</td>
                    <td className="px-4 py-2 text-foreground">{fmt(row.credit_sum)}</td>
                    <td className="px-4 py-2 text-foreground">{fmt(row.balance)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20">
                <tr className="text-sm font-medium text-foreground">
                  <td className="px-4 py-2">Totals</td>
                  <td className="px-4 py-2">{fmt(trialBalanceQuery.data?.total_debit ?? "0")}</td>
                  <td className="px-4 py-2">{fmt(trialBalanceQuery.data?.total_credit ?? "0")}</td>
                  <td className="px-4 py-2">0.00</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-base font-semibold text-foreground">Account Journals</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          {selectedAccountCode
            ? `Posted journals containing account ${selectedAccountCode}`
            : "Select an account row to view related posted journals."}
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
