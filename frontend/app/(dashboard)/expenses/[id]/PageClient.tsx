"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { PolicyViolationBadge } from "@/components/expenses/PolicyViolationBadge"
import { approveExpenseClaim, getExpenseClaim } from "@/lib/api/expenses"
import type { ExpenseApproval, ExpenseClaim } from "@/lib/types/expense"
import { formatINR } from "@/lib/utils"

interface ExpenseDetailPageProps {
  params: {
    id: string
  }
}

export default function ExpenseDetailPage({ params }: ExpenseDetailPageProps) {
  const { data: session } = useSession()
  const role = (session?.user as { role?: string } | undefined)?.role ?? "finance_leader"
  const canApprove = role === "finance_leader" || role === "super_admin" || role === "finance_team"

  const [claim, setClaim] = useState<ExpenseClaim | null>(null)
  const [approvals, setApprovals] = useState<ExpenseApproval[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setError(null)
      const payload = await getExpenseClaim(params.id)
      setClaim(payload)
      setApprovals(payload.approvals)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load expense claim")
    }
  }, [params.id])

  useEffect(() => {
    void load()
  }, [params.id, load])

  const performApproval = async (action: "approved" | "rejected") => {
    setBusy(true)
    try {
      await approveExpenseClaim(params.id, action)
      await load()
    } finally {
      setBusy(false)
    }
  }

  if (!claim) {
    return (
      <div className="space-y-4">
        {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold text-foreground">Expense Claim</h1>
          <span className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">{claim.status}</span>
        </div>
        <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
          <p>Vendor: <span className="text-foreground">{claim.vendor_name}</span></p>
          <p>Amount: <span className="text-foreground">{formatINR(claim.amount)}</span></p>
          <p>Date: <span className="text-foreground">{claim.claim_date}</span></p>
          <p>Category: <span className="text-foreground">{claim.category}</span></p>
          <p className="md:col-span-2">Description: <span className="text-foreground">{claim.description}</span></p>
        </div>
        <div className="mt-3">
          <PolicyViolationBadge
            violation_type={claim.policy_violation_type}
            is_hard_block={claim.policy_violation_type === "hard_limit" || claim.policy_violation_type === "personal_merchant"}
            message={claim.justification ?? undefined}
          />
        </div>
        {canApprove ? (
          <div className="mt-4 flex gap-2">
            <Button onClick={() => void performApproval("approved")} disabled={busy}>Approve</Button>
            <Button variant="outline" onClick={() => void performApproval("rejected")} disabled={busy}>Reject</Button>
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Approval History</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          {approvals.map((approval) => (
            <li key={approval.id} className="rounded-md border border-border px-3 py-2">
              <div className="font-medium text-foreground">{approval.action}</div>
              <div>{approval.approver_role} • {approval.created_at}</div>
              {approval.comments ? <div>Comments: {approval.comments}</div> : null}
            </li>
          ))}
          {approvals.length === 0 ? <li>No approvals yet.</li> : null}
        </ul>
      </section>
    </div>
  )
}
