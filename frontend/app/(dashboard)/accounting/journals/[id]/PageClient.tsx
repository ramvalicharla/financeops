"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import {
  approveJournal,
  getJournal,
  postJournal,
  reviewJournal,
  reverseJournal,
  submitJournal,
} from "@/lib/api/accounting-journals"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import {
  canPerformAction,
  getPermissionDeniedMessage,
} from "@/lib/ui-access"
import { Button } from "@/components/ui/button"

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

export default function JournalDetailPage({ params }: JournalDetailPageProps) {
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const queryClient = useQueryClient()
  const openIntentPanel = useControlPlaneStore((state) => state.openIntentPanel)
  const journalId = params.id
  const journalQuery = useQuery({
    queryKey: ["accounting-journal", journalId],
    queryFn: async () => getJournal(journalId),
  })

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["accounting-journal", journalId] })
    await queryClient.invalidateQueries({ queryKey: ["accounting-journals"] })
  }

  const submitMutation = useMutation({
    mutationFn: () => submitJournal(journalId),
    onSuccess: async (result) => {
      openIntentPanel(result)
      await refresh()
    },
  })
  const reviewMutation = useMutation({
    mutationFn: () => reviewJournal(journalId),
    onSuccess: async (result) => {
      openIntentPanel(result)
      await refresh()
    },
  })
  const approveMutation = useMutation({
    mutationFn: () => approveJournal(journalId),
    onSuccess: async (result) => {
      openIntentPanel(result)
      await refresh()
    },
  })
  const postMutation = useMutation({
    mutationFn: () => postJournal(journalId),
    onSuccess: async (result) => {
      openIntentPanel(result)
      await refresh()
    },
  })
  const reverseMutation = useMutation({
    mutationFn: () => reverseJournal(journalId),
    onSuccess: async (result) => {
      openIntentPanel(result)
      await refresh()
    },
  })

  const journal = journalQuery.data
  const status = journal?.status ?? "DRAFT"
  const actionsDisabled =
    submitMutation.isPending ||
    reviewMutation.isPending ||
    approveMutation.isPending ||
    postMutation.isPending ||
    reverseMutation.isPending

  const canSubmit = status === "DRAFT"
  const canReview = status === "SUBMITTED" && canPerformAction("journal.review", userRole)
  const canApprove = status === "REVIEWED" && canPerformAction("journal.approve", userRole)
  const canPost = status === "APPROVED" && canPerformAction("journal.post", userRole)
  const canReverse = status === "POSTED" && canPerformAction("journal.reverse", userRole)

  const totals = useMemo(
    () => ({
      debit: journal ? formatAmount(journal.total_debit) : "0.00",
      credit: journal ? formatAmount(journal.total_credit) : "0.00",
    }),
    [journal],
  )

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Journal Workflow</h1>
          <p className="text-sm text-muted-foreground">
            Submit, review, approve, post, and reverse using governance lifecycle controls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/accounting/journals">
            <Button variant="outline">Back to Journals</Button>
          </Link>
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
                <p className="mt-1 text-sm font-medium text-foreground">{journal.status}</p>
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
                <p className="mt-1 text-sm text-foreground">{journal.approval_status ?? "-"}</p>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{journal.narration ?? "-"}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {canSubmit ? (
                <Button
                  variant="outline"
                  onClick={() => submitMutation.mutate()}
                  disabled={actionsDisabled || !canPerformAction("journal.submit", userRole)}
                  title={!canPerformAction("journal.submit", userRole) ? getPermissionDeniedMessage("journal.submit") : undefined}
                >
                  Submit
                </Button>
              ) : null}
              {canReview ? (
                <Button variant="outline" onClick={() => reviewMutation.mutate()} disabled={actionsDisabled}>
                  Review
                </Button>
              ) : null}
              {canApprove ? (
                <Button variant="outline" onClick={() => approveMutation.mutate()} disabled={actionsDisabled}>
                  Approve
                </Button>
              ) : null}
              {canPost ? (
                <Button variant="outline" onClick={() => postMutation.mutate()} disabled={actionsDisabled}>
                  Post
                </Button>
              ) : null}
              {canReverse ? (
                <Button variant="outline" onClick={() => reverseMutation.mutate()} disabled={actionsDisabled}>
                  Reverse
                </Button>
              ) : null}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2">Line</th>
                    <th className="px-4 py-2">Account</th>
                    <th className="px-4 py-2">Debit</th>
                    <th className="px-4 py-2">Credit</th>
                    <th className="px-4 py-2">Memo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {journal.lines.map((line) => (
                    <tr key={line.line_number}>
                      <td className="px-4 py-2 text-foreground">{line.line_number}</td>
                      <td className="px-4 py-2 text-foreground">
                        {line.account_code}
                        {line.account_name ? <span className="ml-2 text-muted-foreground">({line.account_name})</span> : null}
                      </td>
                      <td className="px-4 py-2 text-foreground">{formatAmount(line.debit)}</td>
                      <td className="px-4 py-2 text-foreground">{formatAmount(line.credit)}</td>
                      <td className="px-4 py-2 text-muted-foreground">{line.memo ?? "-"}</td>
                    </tr>
                  ))}
                  <tr className="bg-muted/20">
                    <td className="px-4 py-2 text-foreground" colSpan={2}>
                      Totals
                    </td>
                    <td className="px-4 py-2 font-semibold text-foreground">{totals.debit}</td>
                    <td className="px-4 py-2 font-semibold text-foreground">{totals.credit}</td>
                    <td className="px-4 py-2" />
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
