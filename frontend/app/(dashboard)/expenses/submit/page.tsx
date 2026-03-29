"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ExpenseForm } from "@/components/expenses/ExpenseForm"
import { getExpensePolicy } from "@/lib/api/expenses"
import type { ExpenseClaim, ExpensePolicy } from "@/lib/types/expense"

export default function SubmitExpensePage() {
  const router = useRouter()
  const [policy, setPolicy] = useState<ExpensePolicy | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadPolicy = async () => {
      try {
        setPolicy(await getExpensePolicy())
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load expense policy")
      }
    }
    void loadPolicy()
  }, [])

  const onSubmitted = (_claim: ExpenseClaim) => {
    router.push("/expenses")
  }

  if (!policy) {
    return (
      <div className="space-y-4">
        {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
        <div className="h-52 animate-pulse rounded-xl bg-muted" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-foreground">Submit Expense</h1>
      <ExpenseForm policy={policy} onSubmitted={onSubmitted} />
    </div>
  )
}
