"use client"

import Link from "next/link"
import type { ExpenseClaim } from "@/lib/types/expense"
import { formatINR } from "@/lib/utils"
import { PolicyViolationBadge } from "@/components/expenses/PolicyViolationBadge"

interface ExpenseCardProps {
  claim: ExpenseClaim
}

const hardViolations = new Set(["personal_merchant", "hard_limit", "duplicate"])

export function ExpenseCard({ claim }: ExpenseCardProps) {
  return (
    <Link
      href={`/expenses/${claim.id}`}
      className="block rounded-xl border border-border bg-card p-4 transition hover:border-[hsl(var(--brand-primary)/0.6)]"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{claim.vendor_name}</h3>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">{claim.status}</span>
      </div>
      <div className="grid gap-1 text-sm text-muted-foreground">
        <p>{formatINR(claim.amount)} • {claim.category}</p>
        <p>{claim.claim_date}</p>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Submitted by {claim.submitted_by.slice(0, 8)}...</span>
        <PolicyViolationBadge
          violation_type={claim.policy_violation_type}
          is_hard_block={hardViolations.has(claim.policy_violation_type ?? "")}
        />
      </div>
    </Link>
  )
}
