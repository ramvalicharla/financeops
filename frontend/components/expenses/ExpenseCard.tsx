"use client"

import Link from "next/link"
import type { ExpenseClaim } from "@/lib/types/expense"
import { formatINR } from "@/lib/utils"
import { PolicyViolationBadge } from "@/components/expenses/PolicyViolationBadge"

interface ExpenseCardProps {
  claim: ExpenseClaim
  selectable?: boolean
  selected?: boolean
  onSelect?: (selected: boolean) => void
}

const hardViolations = new Set(["personal_merchant", "hard_limit", "duplicate"])

export function ExpenseCard({ claim, selectable, selected, onSelect }: ExpenseCardProps) {
  return (
    <div className={`relative flex flex-col rounded-xl border ${selected ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.03)]" : "border-border bg-card"} transition hover:border-[hsl(var(--brand-primary)/0.6)]`}>
      {selectable && (
        <div className="absolute top-4 left-4 z-10">
          <input
            type="checkbox"
            className="rounded border-border h-4 w-4"
            checked={selected}
            onChange={(e) => onSelect?.(e.target.checked)}
          />
        </div>
      )}
      <Link
        href={`/expenses/${claim.id}`}
        className={`block p-4 ${selectable ? "pl-10" : ""}`}
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
    </div>
  )
}
