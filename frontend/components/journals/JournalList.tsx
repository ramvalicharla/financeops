"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { listJournals, type JournalRecord } from "@/lib/api/accounting-journals"
import { createGovernedIntent } from "@/lib/api/intents"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"
import { FlowStrip } from "@/components/ui/FlowStrip"
import { StateBadge } from "@/components/ui/StateBadge"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/common/DataTable"

const formatAmount = (value: string): string =>
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
  const openTimelinePanel = useControlPlaneStore((state) => state.openTimelinePanel)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const query = useQuery({
    queryKey: ["accounting-journals", activeEntityId],
    queryFn: async () =>
      listJournals(activeEntityId ? { org_entity_id: activeEntityId, limit: 100 } : { limit: 100 }),
  })

  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["accounting-journals"] })
  }

  const onGovernedSuccess = (result: {
    intent_id: string
    status: string
    job_id: string | null
    next_action: string
    record_refs: Record<string, unknown> | null
  }) => {
    openIntentPanel(result)
    refresh()
  }

  const governedMutation = useMutation({
    mutationFn: createGovernedIntent,
    onSuccess: onGovernedSuccess,
  })

  const journals = useMemo(() => query.data ?? [], [query.data])

  const columns = useMemo<DataTableColumn<JournalRecord>[]>(
    () => [
      {
        key: "journal-number",
        header: "Journal #",
        render: (journal) => (
          <Link href={`/accounting/journals/${journal.id}`} className="font-medium text-foreground underline-offset-4 hover:underline">
            {journal.journal_number}
          </Link>
        ),
      },
      {
        key: "date",
        header: "Date",
        render: (journal) => <span className="text-muted-foreground">{journal.journal_date}</span>,
      },
      {
        key: "description",
        header: "Description",
        render: (journal) => <span className="text-muted-foreground">{journal.narration ?? journal.reference ?? "-"}</span>,
      },
      {
        key: "status",
        header: "Status",
        render: (journal) => <StateBadge status={journal.status} />,
      },
      {
        key: "created-by",
        header: "Created By",
        render: (journal) => <span className="font-mono text-xs text-muted-foreground">{journal.created_by ?? "-"}</span>,
      },
      {
        key: "intent",
        header: "Intent ID",
        render: (journal) =>
          journal.intent_id ? (
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
          ),
      },
      {
        key: "job",
        header: "Job ID",
        render: (journal) =>
          journal.job_id ? (
            <button
              type="button"
              className="rounded-full border border-border bg-background px-3 py-1 font-mono text-xs text-foreground"
              onClick={() => openJobPanel(journal.job_id)}
            >
              {journal.job_id}
            </button>
          ) : (
            <span className="text-xs text-muted-foreground">-</span>
          ),
      },
      {
        key: "approval",
        header: "Approval",
        render: (journal) => (
          <StateBadge
            status={journal.approval_status ?? journal.status}
            label={journal.approval_status ?? journal.status}
          />
        ),
      },
      {
        key: "actions",
        header: "Actions",
        render: (journal) => (
          <div className="flex flex-wrap gap-2">
            {journal.status === "DRAFT" && canPerformAction("journal.submit", userRole) ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  governedMutation.mutate({
                    type: "SUBMIT_JOURNAL",
                    data: { journal_id: journal.id },
                  })
                }
                disabled={governedMutation.isPending}
              >
                Submit
              </Button>
            ) : null}
            {journal.status === "SUBMITTED" && canPerformAction("journal.review", userRole) ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  governedMutation.mutate({
                    type: "REVIEW_JOURNAL",
                    data: { journal_id: journal.id },
                  })
                }
                disabled={governedMutation.isPending}
              >
                Review
              </Button>
            ) : null}
            {journal.status === "REVIEWED" && canPerformAction("journal.approve", userRole) ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  governedMutation.mutate({
                    type: "APPROVE_JOURNAL",
                    data: { journal_id: journal.id },
                  })
                }
                disabled={governedMutation.isPending}
              >
                Approve
              </Button>
            ) : null}
            {journal.status === "APPROVED" && canPerformAction("journal.post", userRole) ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  governedMutation.mutate({
                    type: "POST_JOURNAL",
                    data: { journal_id: journal.id },
                  })
                }
                disabled={governedMutation.isPending}
              >
                Post
              </Button>
            ) : null}
            {journal.status === "POSTED" && canPerformAction("journal.reverse", userRole) ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  governedMutation.mutate({
                    type: "REVERSE_JOURNAL",
                    data: { journal_id: journal.id },
                  })
                }
                disabled={governedMutation.isPending}
              >
                Reverse
              </Button>
            ) : null}
            <Button type="button" variant="outline" size="sm" onClick={() => openTimelinePanel("journal", journal.id)}>
              Timeline
            </Button>
            <Link href={`/accounting/journals/${journal.id}`}>
              <Button variant="outline" size="sm">
                Open
              </Button>
            </Link>
          </div>
        ),
      },
    ],
    [governedMutation, openIntentPanel, openJobPanel, openTimelinePanel, userRole],
  )

  if (query.isLoading) {
    return (
      <div className="space-y-3">
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
          No data yet. Start by creating a journal so its intent, approval state, execution trace, and timeline appear here.
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
      <DataTable
        columns={columns}
        rows={journals}
        emptyMessage="No journals returned for the current scope."
        label="Journals"
      />
    </div>
  )
}
