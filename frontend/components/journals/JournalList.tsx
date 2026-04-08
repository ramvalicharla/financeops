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
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"
import { Button } from "@/components/ui/button"

const fmt = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export function JournalList() {
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const queryClient = useQueryClient()
  const openIntentPanel = useControlPlaneStore((state) => state.openIntentPanel)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const query = useQuery({
    queryKey: ["accounting-journals", activeEntityId],
    queryFn: async () =>
      listJournals(activeEntityId ? { org_entity_id: activeEntityId, limit: 100 } : { limit: 100 }),
  })

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["accounting-journals"] })
  }

  const onGovernedSuccess = async (result: {
    intent_id: string
    status: string
    job_id: string | null
    next_action: string
    record_refs: Record<string, unknown> | null
  }) => {
    openIntentPanel(result)
    await refresh()
  }

  const approveMutation = useMutation({
    mutationFn: (journalId: string) => approveJournal(journalId),
    onSuccess: onGovernedSuccess,
  })
  const submitMutation = useMutation({
    mutationFn: (journalId: string) => submitJournal(journalId),
    onSuccess: onGovernedSuccess,
  })
  const reviewMutation = useMutation({
    mutationFn: (journalId: string) => reviewJournal(journalId),
    onSuccess: onGovernedSuccess,
  })
  const postMutation = useMutation({
    mutationFn: (journalId: string) => postJournal(journalId),
    onSuccess: onGovernedSuccess,
  })
  const reverseMutation = useMutation({
    mutationFn: (journalId: string) => reverseJournal(journalId),
    onSuccess: onGovernedSuccess,
  })

  const journals = useMemo(() => query.data ?? [], [query.data])

  if (query.isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    )
  }

  if (query.error) {
    return <div className="text-sm text-[hsl(var(--brand-danger))]">Failed to load journals.</div>
  }

  if (!journals.length) {
    return <div className="text-sm text-muted-foreground">No journals available in the current scope.</div>
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/30">
          <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2">Journal #</th>
            <th className="px-4 py-2">Date</th>
            <th className="px-4 py-2">Description</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Created By</th>
            <th className="px-4 py-2">Intent ID</th>
            <th className="px-4 py-2">Job ID</th>
            <th className="px-4 py-2">Approval</th>
            <th className="px-4 py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {journals.map((journal) => (
            <tr key={journal.id}>
              <td className="px-4 py-2 font-medium text-foreground">{journal.journal_number}</td>
              <td className="px-4 py-2 text-muted-foreground">{journal.journal_date}</td>
              <td className="px-4 py-2 text-muted-foreground">{journal.narration ?? journal.reference ?? "-"}</td>
              <td className="px-4 py-2 text-foreground">{journal.status}</td>
              <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{journal.created_by ?? "-"}</td>
              <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{journal.intent_id ?? "-"}</td>
              <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{journal.job_id ?? "-"}</td>
              <td className="px-4 py-2 text-muted-foreground">{journal.approval_status ?? "-"}</td>
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
                    <Button variant="outline" onClick={() => reviewMutation.mutate(journal.id)} disabled={reviewMutation.isPending}>
                      Review
                    </Button>
                  ) : null}
                  {journal.status === "REVIEWED" && canPerformAction("journal.approve", userRole) ? (
                    <Button variant="outline" onClick={() => approveMutation.mutate(journal.id)} disabled={approveMutation.isPending}>
                      Approve
                    </Button>
                  ) : null}
                  {journal.status === "APPROVED" && canPerformAction("journal.post", userRole) ? (
                    <Button variant="outline" onClick={() => postMutation.mutate(journal.id)} disabled={postMutation.isPending}>
                      Post
                    </Button>
                  ) : null}
                  {journal.status === "POSTED" && canPerformAction("journal.reverse", userRole) ? (
                    <Button variant="outline" onClick={() => reverseMutation.mutate(journal.id)} disabled={reverseMutation.isPending}>
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
  )
}
