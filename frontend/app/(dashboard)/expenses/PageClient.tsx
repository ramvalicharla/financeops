"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { Plus } from "lucide-react"
import { ExpenseCard } from "@/components/expenses/ExpenseCard"
import { listExpenses } from "@/lib/api/expenses"
import type { ExpenseClaim } from "@/lib/types/expense"

const statuses = ["all", "submitted", "approved", "rejected", "paid"] as const

export default function ExpensesPage() {
  const { data: session } = useSession()
  const role = (session?.user as { role?: string } | undefined)?.role ?? "finance_leader"
  const canViewTeam = role === "finance_leader" || role === "super_admin" || role === "finance_team"

  const [tab, setTab] = useState<"my" | "team">("my")
  const [statusFilter, setStatusFilter] = useState<(typeof statuses)[number]>("all")
  const [rows, setRows] = useState<ExpenseClaim[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const payload = await listExpenses({
          status: statusFilter === "all" ? undefined : statusFilter,
          limit: 50,
        })
        const userId = (session?.user as { id?: string } | undefined)?.id
        if (tab === "my" && userId) {
          setRows(payload.data.filter((row) => row.submitted_by === userId))
        } else if (tab === "my") {
          setRows(payload.data)
        } else {
          setRows(payload.data)
        }
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load expenses")
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [session, statusFilter, tab])

  const visibleRows = useMemo(() => rows, [rows])

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Expenses</h1>
          <p className="text-sm text-muted-foreground">Submit, review, and approve claims.</p>
        </div>
        <Link
          href="/expenses/submit"
          className="fixed bottom-8 right-8 inline-flex h-12 w-12 items-center justify-center rounded-full bg-[hsl(var(--brand-primary))] text-black shadow-lg"
          aria-label="New expense"
        >
          <Plus className="h-5 w-5" />
        </Link>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={`rounded-md px-3 py-2 text-sm ${tab === "my" ? "bg-accent text-foreground" : "text-muted-foreground"}`} onClick={() => setTab("my")}>My Expenses</button>
        {canViewTeam ? (
          <button type="button" className={`rounded-md px-3 py-2 text-sm ${tab === "team" ? "bg-accent text-foreground" : "text-muted-foreground"}`} onClick={() => setTab("team")}>Team Expenses</button>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        {statuses.map((status) => (
          <button
            key={status}
            type="button"
            className={`rounded-full border px-3 py-1 text-xs ${statusFilter === status ? "border-[hsl(var(--brand-primary))] text-foreground" : "border-border text-muted-foreground"}`}
            onClick={() => setStatusFilter(status)}
          >
            {status}
          </button>
        ))}
      </div>

      {loading ? <div className="h-40 animate-pulse rounded-lg bg-muted" /> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleRows.map((claim) => (
          <ExpenseCard key={claim.id} claim={claim} />
        ))}
      </div>
    </div>
  )
}
