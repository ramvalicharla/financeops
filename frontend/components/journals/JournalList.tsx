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
import { FlowStrip } from "@/components/ui/FlowStrip"
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
  const openJobPanel = useControlPlaneStore((state) => state.openJobPanel)
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
        <FlowStrip
          title="Journal Flow"
          subtitle="Create, validate, approve, execute, and record through the governed accounting path."
          steps={[
            { label: "Create" },
            { label: "Intent" },
            { label: "Validate" },
            { label: "Approve" },
            { label: "Execute" },
            { label: "Record" },
          ]}
        />
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    )
  }

  if (query.error) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Journal Flow"
          subtitle="Create, validate, approve, execute, and record through the governed accounting path."
          steps={[
            { label: "Create" },
            { label: "Intent" },
            { label: "Validate" },
            { label: "Approve" },
            { label: "Execute" },
            { label: "Record" },
          ]}
        />
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Journals failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {query.error instanceof Error ? query.error.message : "The backend did not return journal rows."}
          </p>
          <p className="mt-2 text-muted-foreground">Refresh the page or switch to a valid entity scope.</p>
        </div>
      </div>
    )
  }

  if (!journals.length) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Journal Flow"
          subtitle="Create, validate, approve, execute, and record through the governed accounting path."
          steps={[
            { label: "Create" },
            { label: "Intent" },
            { label: "Validate" },
            { label: "Approve" },
            { label: "Execute" },
            { label: "Record" },
          ]}
        />
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          No data yet. Start by creating a journal so its intent, approval state, and execution trace appear here.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <FlowStrip
        title="Journal Flow"
        subtitle="Create, validate, approve, execute, and record through the governed accounting path."
        steps={[
          { label: "Create" },
          { label: "Intent" },
          { label: "Validate" },
          { label: "Approve" },
          { label: "Execute" },
          { label: "Record" },
        ]}
      />
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
              <td className="px-4 py-2">
                {journal.intent_id ? (
                  <button
                    type="button"
                    className="rounded-full border border-[hsl(var(--brand-primary)/0.25)] bg-[hsl(var(--brand-primary)/0.08)] px-3 py-1 font-mono text-xs text-foreground"
                    onClick={() =>
                      openIntentPanel({
                        intent_id: journal.intent_id!,
                        status: journal.status,
                        job_id: journal.job_id,
                        next_action: journal.approval_status ?? null,
                        record_refs: { journal_id: journal.id },
                      })
                    }
                  >
                    {journal.intent_id}
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">-</span>
                )}
              </td>
              <td className="px-4 py-2">
                {journal.job_id ? (
                  <button
                    type="button"
                    className="rounded-full border border-border bg-background px-3 py-1 font-mono text-xs text-foreground"
                    onClick={() => openJobPanel(journal.job_id)}
                  >
                    {journal.job_id}
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">-</span>
                )}
              </td>
              <td className="px-4 py-2">
                <span className="rounded-full bg-[hsl(var(--brand-success)/0.12)] px-3 py-1 text-xs font-medium text-foreground">
                  {journal.approval_status ?? "-"}
                </span>
              </td>
              <td className="px-4 py-2">
                <div className="flex flex-wrap gap-2">
                  {journal.status === "DRAFT" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => submitMutation.mutate(journal.id)}
                      disabled={submitMutation.isPending || !canPerformAction("journal.submit", userRole)}
                      title={!canPerformAction("journal.submit", userRole) ? getPermissionDeniedMessage("journal.submit") : undefined}
                    >
                      Submit
                    </Button>
                  ) : null}
                  {journal.status === "SUBMITTED" && canPerformAction("journal.review", userRole) ? (
                    <Button variant="outline" size="sm" onClick={() => reviewMutation.mutate(journal.id)} disabled={reviewMutation.isPending}>
                      Review
                    </Button>
                  ) : null}
                  {journal.status === "REVIEWED" && canPerformAction("journal.approve", userRole) ? (
                    <Button variant="outline" size="sm" onClick={() => approveMutation.mutate(journal.id)} disabled={approveMutation.isPending}>
                      Approve
                    </Button>
                  ) : null}
                  {journal.status === "APPROVED" && canPerformAction("journal.post", userRole) ? (
                    <Button variant="outline" size="sm" onClick={() => postMutation.mutate(journal.id)} disabled={postMutation.isPending}>
                      Post
                    </Button>
                  ) : null}
                  {journal.status === "POSTED" && canPerformAction("journal.reverse", userRole) ? (
                    <Button variant="outline" size="sm" onClick={() => reverseMutation.mutate(journal.id)} disabled={reverseMutation.isPending}>
                      Reverse
                    </Button>
                  ) : null}
                  <Link href={`/accounting/journals/${journal.id}`}>
                    <Button variant="outline" size="sm">Open</Button>
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  )
}
