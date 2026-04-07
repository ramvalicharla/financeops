"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { completeChecklistItem, getCloseChecklist } from "@/lib/api/close-governance"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const parsePeriod = (value: string): { fiscalYear: number; periodNumber: number } => {
  const [yearText, monthText] = value.split("-")
  const fiscalYear = Number.parseInt(yearText, 10)
  const periodNumber = Number.parseInt(monthText, 10)
  return {
    fiscalYear: Number.isFinite(fiscalYear) ? fiscalYear : new Date().getFullYear(),
    periodNumber: Number.isFinite(periodNumber) ? periodNumber : new Date().getMonth() + 1,
  }
}

export default function CloseChecklistPage() {
  const queryClient = useQueryClient()
  const searchParams = useSearchParams()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const initialPeriod = searchParams?.get("period") ?? new Date().toISOString().slice(0, 7)
  const [period, setPeriod] = useState(initialPeriod)
  const { fiscalYear, periodNumber } = useMemo(() => parsePeriod(period), [period])

  const checklistQuery = useQuery({
    queryKey: ["close-checklist", activeEntityId, fiscalYear, periodNumber],
    queryFn: async () =>
      getCloseChecklist({
        org_entity_id: activeEntityId as string,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
      }),
    enabled: Boolean(activeEntityId),
  })

  const completeMutation = useMutation({
    mutationFn: (checklistType: string) =>
      completeChecklistItem({
        org_entity_id: activeEntityId as string,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
        checklist_type: checklistType,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["close-checklist"] })
      await queryClient.invalidateQueries({ queryKey: ["close-readiness"] })
    },
  })

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Close Checklist</h1>
          <p className="text-sm text-muted-foreground">
            Period-close tasks, evidence completion, and readiness blockers.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            type="month"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          />
          <Link href={`/close?period=${period}`}>
            <Button variant="outline">Back to Close</Button>
          </Link>
        </div>
      </header>

      {!activeEntityId ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Select an active entity to load checklist items.</p>
        </section>
      ) : checklistQuery.isLoading ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Loading checklist...</p>
        </section>
      ) : checklistQuery.error ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load checklist.</p>
        </section>
      ) : (
        <>
          <section className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-base font-semibold text-foreground">Readiness Summary</h2>
            <p className="mt-2 text-sm text-foreground">
              Status:{" "}
              <span className={checklistQuery.data?.readiness.pass ? "text-emerald-400" : "text-amber-400"}>
                {checklistQuery.data?.readiness.pass ? "PASS" : "FAIL"}
              </span>
            </p>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-foreground">Blockers</p>
                {checklistQuery.data?.readiness.blockers.length ? (
                  <ul className="ml-5 list-disc text-sm text-[hsl(var(--brand-danger))]">
                    {checklistQuery.data.readiness.blockers.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No blockers.</p>
                )}
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Warnings</p>
                {checklistQuery.data?.readiness.warnings.length ? (
                  <ul className="ml-5 list-disc text-sm text-amber-300">
                    {checklistQuery.data.readiness.warnings.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No warnings.</p>
                )}
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2">Checklist Item</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Completed At</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {checklistQuery.data?.items.map((item) => (
                    <tr key={item.checklist_type}>
                      <td className="px-4 py-2 text-foreground">{item.checklist_type}</td>
                      <td className="px-4 py-2 text-muted-foreground">{item.checklist_status}</td>
                      <td className="px-4 py-2 text-muted-foreground">{item.completed_at ?? "-"}</td>
                      <td className="px-4 py-2">
                        <Button
                          variant="outline"
                          disabled={item.checklist_status === "COMPLETED" || completeMutation.isPending}
                          onClick={() => completeMutation.mutate(item.checklist_type)}
                        >
                          Mark Complete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
