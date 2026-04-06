"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import {
  approveJournal,
  listJournals,
  postJournal,
  reviewJournal,
  reverseJournal,
  submitJournal,
} from "@/lib/api/accounting-journals"
import { useTenantStore } from "@/lib/store/tenant"
import {
  canPerformAction,
  getPermissionDeniedMessage,
} from "@/lib/ui-access"
import { Button } from "@/components/ui/button"

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export default function JournalsPage() {
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const canCreateJournal = canPerformAction("journal.create", userRole)
  const queryClient = useQueryClient()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const query = useQuery({
    queryKey: ["accounting-journals", activeEntityId],
    queryFn: async () =>
      listJournals(activeEntityId ? { org_entity_id: activeEntityId, limit: 100 } : { limit: 100 }),
  })
  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["accounting-journals"] })
  }
  const approveMutation = useMutation({
    mutationFn: (journalId: string) => approveJournal(journalId),
    onSuccess: refresh,
  })
  const submitMutation = useMutation({
    mutationFn: (journalId: string) => submitJournal(journalId),
    onSuccess: refresh,
  })
  const reviewMutation = useMutation({
    mutationFn: (journalId: string) => reviewJournal(journalId),
    onSuccess: refresh,
  })
  const postMutation = useMutation({
    mutationFn: (journalId: string) => postJournal(journalId),
    onSuccess: refresh,
  })
  const reverseMutation = useMutation({
    mutationFn: (journalId: string) => reverseJournal(journalId),
    onSuccess: refresh,
  })

  const journals = useMemo(() => query.data ?? [], [query.data])

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Journals</h1>
          <p className="text-sm text-muted-foreground">
            Draft, approved, and posted journals for the active tenant/entity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/trial-balance">
            <Button variant="outline">Trial Balance</Button>
          </Link>
          {canCreateJournal ? (
            <Link href="/accounting/journals/new">
              <Button>Create Journal</Button>
            </Link>
          ) : (
            <Button
              disabled
              title={getPermissionDeniedMessage("journal.create")}
            >
              Create Journal
            </Button>
          )}
        </div>
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
                  <th className="px-4 py-2">Actions</th>
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
                      <span
                        className={
                          journal.status === "POSTED"
                            ? "rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300"
                            : journal.status === "APPROVED"
                              ? "rounded-full bg-amber-500/15 px-2 py-1 text-xs text-amber-300"
                              : "rounded-full bg-slate-500/15 px-2 py-1 text-xs text-slate-300"
                        }
                      >
                        {journal.status}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-2">
                        {journal.status === "DRAFT" ? (
                          <Button
                            variant="outline"
                            onClick={() => submitMutation.mutate(journal.id)}
                            disabled={submitMutation.isPending || !canPerformAction("journal.submit", userRole)}
                            title={!canPerformAction("journal.submit", userRole) ? getPermissionDeniedMessage("journal.submit") : undefined}
                          >
                            Submit
                          </Button>
                        ) : null}
                        {journal.status === "SUBMITTED" && canPerformAction("journal.review", userRole) ? (
                          <Button
                            variant="outline"
                            onClick={() => reviewMutation.mutate(journal.id)}
                            disabled={reviewMutation.isPending}
                          >
                            Review
                          </Button>
                        ) : null}
                        {journal.status === "REVIEWED" && canPerformAction("journal.approve", userRole) ? (
                          <Button
                            variant="outline"
                            onClick={() => approveMutation.mutate(journal.id)}
                            disabled={approveMutation.isPending}
                          >
                            Approve
                          </Button>
                        ) : null}
                        {journal.status === "APPROVED" && canPerformAction("journal.post", userRole) ? (
                          <Button
                            variant="outline"
                            onClick={() => postMutation.mutate(journal.id)}
                            disabled={postMutation.isPending}
                          >
                            Post
                          </Button>
                        ) : null}
                        {journal.status === "POSTED" && canPerformAction("journal.reverse", userRole) ? (
                          <Button
                            variant="outline"
                            onClick={() => reverseMutation.mutate(journal.id)}
                            disabled={reverseMutation.isPending}
                          >
                            Reverse
                          </Button>
                        ) : null}
                        <Link href={`/accounting/journals/${journal.id}`}>
                          <Button variant="outline">Open</Button>
                        </Link>
                      </div>
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
