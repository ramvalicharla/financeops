"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJournals } from "@/lib/api/accounting-journals"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function JournalsPage() {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const query = useQuery({
    queryKey: ["accounting-journals", activeEntityId],
    queryFn: async () =>
      listJournals(activeEntityId ? { org_entity_id: activeEntityId, limit: 100 } : { limit: 100 }),
  })

  const journals = useMemo(() => query.data ?? [], [query.data])

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Journals</h1>
          <p className="text-sm text-muted-foreground">
            Posted accounting journals for the active tenant/entity.
          </p>
        </div>
        <Link href="/accounting/journals/new">
          <Button>Create Journal</Button>
        </Link>
      </header>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : query.error ? (
          <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">
            Failed to load journals.
          </div>
        ) : journals.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">
            No journals posted yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Journal #</th>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Reference</th>
                  <th className="px-4 py-2">Narration</th>
                  <th className="px-4 py-2">Debit</th>
                  <th className="px-4 py-2">Credit</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {journals.map((journal) => (
                  <tr key={journal.id}>
                    <td className="px-4 py-2 font-medium text-foreground">{journal.journal_number}</td>
                    <td className="px-4 py-2 text-muted-foreground">{journal.journal_date}</td>
                    <td className="px-4 py-2 text-muted-foreground">{journal.reference ?? "-"}</td>
                    <td className="px-4 py-2 text-muted-foreground">{journal.narration ?? "-"}</td>
                    <td className="px-4 py-2 text-foreground">{fmt(journal.total_debit)}</td>
                    <td className="px-4 py-2 text-foreground">{fmt(journal.total_credit)}</td>
                    <td className="px-4 py-2">
                      <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300">
                        {journal.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
