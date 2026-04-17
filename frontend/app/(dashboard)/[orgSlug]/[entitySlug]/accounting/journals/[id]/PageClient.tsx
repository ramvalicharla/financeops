"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { getJournal, type JournalLine } from "@/lib/api/accounting-journals"
import { createGovernedIntent, type JournalIntentPayload } from "@/lib/api/intents"
import { listTimeline, type TimelineEvent } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"
import { Button } from "@/components/ui/button"
import { StateBadge } from "@/components/ui/StateBadge"
import { DataTable, type DataTableColumn } from "@/components/common/DataTable"

interface JournalDetailPageProps {
  params: {
    id: string
  }
}

const formatAmount = (value: string): string =>
  Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

const formatTimelineValue = (value: unknown): string => {
  if (typeof value === "string") {
    return value
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`
  }
  if (value && typeof value === "object") {
    return "structured data"
  }
  return "-"
}

const summarizeTimelinePayload = (payload: Record<string, unknown> | null): string => {
  if (!payload) {
    return "No payload details"
  }
  const entries = Object.entries(payload).slice(0, 3)
  if (!entries.length) {
    return "No payload details"
  }
  return entries
    .map(([key, value]) => `${key}: ${formatTimelineValue(value)}`)
    .join(" • ")
}

export default function JournalDetailPage({ params }: JournalDetailPageProps) {
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const queryClient = useQueryClient()
  const openIntentPanel = useControlPlaneStore((state) => state.openIntentPanel)
  const openTimelinePanel = useControlPlaneStore((state) => state.openTimelinePanel)
  const journalId = params.id
  const journalQuery = useQuery({
    queryKey: ["accounting-journal", journalId],
    queryFn: async () => getJournal(journalId),
  })

  const timelineQuery = useQuery({
    queryKey: controlPlaneQueryKeys.timeline({
      subject_type: "journal",
      subject_id: journalId,
      limit: 25,
    }),
    queryFn: async () =>
      listTimeline({
        subject_type: "journal",
        subject_id: journalId,
        limit: 25,
      }),
  })

  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["accounting-journal", journalId] })
    void queryClient.invalidateQueries({ queryKey: ["accounting-journals"] })
    void queryClient.invalidateQueries({
      queryKey: controlPlaneQueryKeys.timeline({ subject_type: "journal", subject_id: journalId, limit: 25 }),
    })
  }

  const onIntentCreated = (result: {
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
    onSuccess: onIntentCreated,
  })

  const journal = journalQuery.data
  const status = journal?.status ?? "DRAFT"
  const actionsDisabled = governedMutation.isPending

  const canSubmit = status === "DRAFT" && canPerformAction("journal.submit", userRole)
  const canReview =
    ["SUBMITTED", "PENDING_REVIEW", "RESUBMITTED"].includes(status) &&
    canPerformAction("journal.review", userRole)
  const canApprove = status === "UNDER_REVIEW" && canPerformAction("journal.approve", userRole)
  const canPost = status === "APPROVED" && canPerformAction("journal.post", userRole)
  const canReverse = status === "PUSHED" && canPerformAction("journal.reverse", userRole)

  const lineColumns = useMemo<DataTableColumn<JournalLine>[]>(
    () => [
      {
        key: "line",
        header: "Line",
        render: (line) => <span className="text-foreground">{line.line_number}</span>,
      },
      {
        key: "account",
        header: "Account",
        render: (line) => (
          <span className="text-foreground">
            {line.account_code}
            {line.account_name ? (
              <span className="ml-2 text-muted-foreground">({line.account_name})</span>
            ) : null}
          </span>
        ),
      },
      {
        key: "debit",
        header: "Debit",
        render: (line) => <span className="text-foreground">{formatAmount(line.debit)}</span>,
      },
      {
        key: "credit",
        header: "Credit",
        render: (line) => <span className="text-foreground">{formatAmount(line.credit)}</span>,
      },
      {
        key: "memo",
        header: "Memo",
        render: (line) => <span className="text-muted-foreground">{line.memo ?? "-"}</span>,
      },
    ],
    [],
  )

  const timelineColumns = useMemo<DataTableColumn<TimelineEvent>[]>(
    () => [
      {
        key: "event",
        header: "Event",
        render: (event) => <StateBadge status={event.timeline_type} label={event.timeline_type.replace(/_/g, " ")} />,
      },
      {
        key: "time",
        header: "Time",
        render: (event) => <span className="text-muted-foreground">{event.occurred_at}</span>,
      },
      {
        key: "actor",
        header: "Actor",
        render: (event) => <span className="text-muted-foreground">{String(event.actor_user_id ?? "system")}</span>,
      },
      {
        key: "summary",
        header: "Summary",
        render: (event) => <span className="text-muted-foreground">{summarizeTimelinePayload(event.payload)}</span>,
      },
    ],
    [],
  )

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Journal Workflow</h1>
          <p className="text-sm text-muted-foreground">
            Submit, review, approve, post, reverse, and inspect the journal timeline without blocking execution.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/journals">
            <Button variant="outline">Back to Journals</Button>
          </Link>
          <Button
            type="button"
            variant="outline"
            onClick={() => openTimelinePanel("journal", journalId)}
            disabled={!journal}
          >
            Open Timeline
          </Button>
        </div>
      </header>

      {journalQuery.isLoading ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Loading journal...</p>
        </section>
      ) : journalQuery.error || !journal ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load journal details.</p>
        </section>
      ) : (
        <>
          <section className="rounded-xl border border-border bg-card p-5">
            <div className="grid gap-3 md:grid-cols-4">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Journal #</p>
                <p className="mt-1 text-sm font-medium text-foreground">{journal.journal_number}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Date</p>
                <p className="mt-1 text-sm text-foreground">{journal.journal_date}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Status</p>
                <div className="mt-1">
                  <StateBadge status={journal.status} />
                </div>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Reference</p>
                <p className="mt-1 text-sm text-foreground">{journal.reference ?? "-"}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Intent ID</p>
                <p className="mt-1 break-all font-mono text-xs text-foreground">{journal.intent_id ?? "-"}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Job ID</p>
                <p className="mt-1 break-all font-mono text-xs text-foreground">{journal.job_id ?? "-"}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Approval Status</p>
                <div className="mt-1">
                  <StateBadge status={journal.approval_status ?? journal.status} label={journal.approval_status ?? journal.status} />
                </div>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{journal.narration ?? "-"}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {canSubmit ? (
                <Button
                  variant="outline"
                  onClick={() =>
                    governedMutation.mutate({
                      type: "SUBMIT_JOURNAL",
                      data: { journal_id: journalId },
                    } satisfies JournalIntentPayload)
                  }
                  disabled={actionsDisabled}
                >
                  Submit
                </Button>
              ) : null}
              {canReview ? (
                <Button
                  variant="outline"
                  onClick={() =>
                    governedMutation.mutate({
                      type: "REVIEW_JOURNAL",
                      data: { journal_id: journalId },
                    } satisfies JournalIntentPayload)
                  }
                  disabled={actionsDisabled}
                >
                  Review
                </Button>
              ) : null}
              {canApprove ? (
                <Button
                  variant="outline"
                  onClick={() =>
                    governedMutation.mutate({
                      type: "APPROVE_JOURNAL",
                      data: { journal_id: journalId },
                    } satisfies JournalIntentPayload)
                  }
                  disabled={actionsDisabled}
                >
                  Approve
                </Button>
              ) : null}
              {canPost ? (
                <Button
                  variant="outline"
                  onClick={() =>
                    governedMutation.mutate({
                      type: "POST_JOURNAL",
                      data: { journal_id: journalId },
                    } satisfies JournalIntentPayload)
                  }
                  disabled={actionsDisabled}
                >
                  Post
                </Button>
              ) : null}
              {canReverse ? (
                <Button
                  variant="outline"
                  onClick={() =>
                    governedMutation.mutate({
                      type: "REVERSE_JOURNAL",
                      data: { journal_id: journalId },
                    } satisfies JournalIntentPayload)
                  }
                  disabled={actionsDisabled}
                >
                  Reverse
                </Button>
              ) : null}
            </div>
            {!canPerformAction("journal.submit", userRole) && status === "DRAFT" ? (
              <p className="mt-3 text-xs text-muted-foreground">
                {getPermissionDeniedMessage("journal.submit")}
              </p>
            ) : null}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Journal Lines
              </h2>
            </div>
            <DataTable
              columns={lineColumns}
              rows={journal.lines}
              emptyMessage="No journal lines were returned."
              label="Journal lines"
            />
          </section>

          <section className="space-y-3 rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Timeline</h2>
                <p className="text-sm text-muted-foreground">
                  Backend events for this journal, rendered as a structured timeline.
                </p>
              </div>
              <Button type="button" variant="outline" onClick={() => void timelineQuery.refetch()}>
                Refresh Timeline
              </Button>
            </div>
            {timelineQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading journal timeline...</p>
            ) : timelineQuery.error ? (
              <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
                <p className="font-medium text-foreground">Journal timeline failed to load</p>
                <p className="mt-1 text-muted-foreground">
                  {timelineQuery.error instanceof Error
                    ? timelineQuery.error.message
                    : "The backend did not return journal timeline data."}
                </p>
              </div>
            ) : !(timelineQuery.data?.length ?? 0) ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
                No timeline events were returned for this journal yet.
              </div>
            ) : (
              <DataTable
                columns={timelineColumns}
                rows={timelineQuery.data ?? []}
                emptyMessage="No timeline events were returned."
                label="Journal timeline"
              />
            )}
          </section>
        </>
      )}
    </div>
  )
}
