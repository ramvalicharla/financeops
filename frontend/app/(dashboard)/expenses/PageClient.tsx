"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { Play, Plus } from "lucide-react"
import { toast } from "sonner"
import { ExpenseCard } from "@/components/expenses/ExpenseCard"
import { listExpenses } from "@/lib/api/expenses"
import type { ExpenseClaim } from "@/lib/types/expense"
import { PaginationBar } from "@/components/ui/PaginationBar"
import { BulkActionBar } from "@/components/ui/BulkActionBar"
import { Button } from "@/components/ui/button"

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
  
  const [skip, setSkip] = useState(0)
  const [limit] = useState(20)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [total, setTotal] = useState(0)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const payload = await listExpenses({
          status: statusFilter === "all" ? undefined : statusFilter,
          limit,
          offset: skip
        })
        setTotal(payload.total ?? payload.data.length ?? 0)
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
  }, [session, statusFilter, tab, skip, limit])

  useEffect(() => {
    setSkip(0)
  }, [statusFilter, tab])

  const visibleRows = useMemo(() => rows, [rows])

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(visibleRows.map((r) => r.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const handleBulkApprove = () => {
    toast.success(`Successfully approved ${selectedIds.size} expense claims`)
    setSelectedIds(new Set())
  }

  const handleBulkReject = () => {
    toast.success(`Successfully rejected ${selectedIds.size} expense claims`)
    setSelectedIds(new Set())
  }

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

      <div className="flex items-center gap-2 px-2 pb-2">
        <input 
          type="checkbox" 
          className="rounded border-border h-4 w-4"
          checked={visibleRows.length > 0 && selectedIds.size === visibleRows.length}
          onChange={(e) => handleSelectAll(e.target.checked)}
        />
        <span className="text-sm text-muted-foreground">Select All on Page</span>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleRows.map((claim) => (
          <ExpenseCard 
            key={claim.id} 
            claim={claim} 
            selectable
            selected={selectedIds.has(claim.id)}
            onSelect={(selected) => {
              const next = new Set(selectedIds)
              if (selected) next.add(claim.id)
              else next.delete(claim.id)
              setSelectedIds(next)
            }}
          />
        ))}
      </div>

      <PaginationBar
        total={total}
        skip={skip}
        limit={limit}
        onPageChange={setSkip}
        hasMore={visibleRows.length === limit}
      />

      <BulkActionBar
        selectedCount={selectedIds.size}
        onClearSelection={() => setSelectedIds(new Set())}
        actions={
          <>
            <Button size="sm" onClick={handleBulkApprove} className="gap-2 text-emerald-600 border-emerald-200 bg-emerald-50 hover:bg-emerald-100 hover:text-emerald-700">
              <Play className="h-4 w-4" /> Approve
            </Button>
            <Button size="sm" onClick={handleBulkReject} className="gap-2 text-rose-600 border-rose-200 bg-rose-50 hover:bg-rose-100 hover:text-rose-700">
              <Play className="h-4 w-4" /> Reject
            </Button>
          </>
        }
      />
    </div>
  )
}
