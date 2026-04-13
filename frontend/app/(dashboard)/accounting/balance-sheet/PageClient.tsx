"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJournals } from "@/lib/api/accounting-journals"
import { getAccountingBalanceSheet, type BalanceSheetItem } from "@/lib/api/accounting-statements"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const today = new Date().toISOString().slice(0, 10)

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function AccountingBalanceSheetPage() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [asOfDate, setAsOfDate] = useState(today)
  const [selectedAccountCode, setSelectedAccountCode] = useState<string | null>(null)

  const balanceSheetQuery = useQuery({
    queryKey: ["accounting-balance-sheet", activeEntityId, asOfDate],
    enabled: Boolean(activeEntityId && asOfDate),
    queryFn: async () =>
      getAccountingBalanceSheet({
        org_entity_id: activeEntityId as string,
        as_of_date: asOfDate,
      }),
  })

  const journalsQuery = useQuery({
    queryKey: ["accounting-journals-bs", activeEntityId],
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

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Balance Sheet</h1>
          <p className="text-sm text-muted-foreground">
            Asset, liability, and equity balances as of a selected date.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/pnl">
            <Button variant="outline">P&L</Button>
          </Link>
          <Link href="/accounting/cash-flow">
            <Button variant="outline">Cash Flow</Button>
          </Link>
        </div>
      </header>

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">As of date</span>
          <input
            type="date"
            value={asOfDate}
            onChange={(event) => setAsOfDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          />
        </label>
        <div className="flex items-end">
          <Button
            variant="outline"
            onClick={() => void balanceSheetQuery.refetch()}
            disabled={balanceSheetQuery.isFetching || !activeEntityId}
          >
            Refresh
          </Button>
        </div>
      </section>

      {balanceSheetQuery.data ? (
        <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
          <Metric label="Total Assets" value={balanceSheetQuery.data.totals.assets} />
          <Metric label="Total Liabilities" value={balanceSheetQuery.data.totals.liabilities} />
          <Metric label="Total Equity" value={balanceSheetQuery.data.totals.equity} />
          <Metric
            label="Liabilities + Equity"
            value={balanceSheetQuery.data.totals.liabilities_and_equity}
          />
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <BalanceSection
          title="Assets"
          items={balanceSheetQuery.data?.assets ?? []}
          onSelectAccount={setSelectedAccountCode}
        />
        <BalanceSection
          title="Liabilities"
          items={balanceSheetQuery.data?.liabilities ?? []}
          onSelectAccount={setSelectedAccountCode}
        />
        <BalanceSection
          title="Equity"
          items={balanceSheetQuery.data?.equity ?? []}
          onSelectAccount={setSelectedAccountCode}
        />
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

function BalanceSection({
  title,
  items,
  onSelectAccount,
}: {
  title: string
  items: BalanceSheetItem[]
  onSelectAccount: (code: string) => void
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <header className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
      </header>
      {items.length === 0 ? (
        <p className="p-4 text-sm text-muted-foreground">No rows.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Account</th>
                <th className="px-4 py-2">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((item) => (
                <tr
                  key={`${title}-${item.account_code}`}
                  className="cursor-pointer hover:bg-muted/20"
                  onClick={() => onSelectAccount(item.account_code)}
                >
                  <td className="px-4 py-2">
                    <p className="font-medium text-foreground">{item.account_name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{item.account_code}</p>
                  </td>
                  <td className="px-4 py-2 text-foreground">{fmt(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
