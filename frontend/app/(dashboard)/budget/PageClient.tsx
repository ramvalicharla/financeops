"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { PlusCircle } from "lucide-react"
import { createBudgetVersion, listBudgetVersions } from "@/lib/api/budget"
import type { BudgetVersion } from "@/lib/types/budget"

export default function BudgetHomePage() {
  const router = useRouter()
  const currentYear = new Date().getFullYear()
  const [rows, setRows] = useState<BudgetVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const payload = await listBudgetVersions({ fiscal_year: currentYear, limit: 100, offset: 0 })
        setRows(payload.data)
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load budgets")
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [currentYear])

  const grouped = useMemo(() => {
    const map = new Map<number, BudgetVersion[]>()
    for (const row of rows) {
      const existing = map.get(row.fiscal_year) ?? []
      existing.push(row)
      map.set(row.fiscal_year, existing)
    }
    return Array.from(map.entries()).sort((a, b) => b[0] - a[0])
  }, [rows])

  const createCurrentYearBudget = async () => {
    setCreating(true)
    try {
      await createBudgetVersion({
        fiscal_year: currentYear,
        version_name: `Annual Budget ${currentYear} v1`,
      })
      router.push(`/budget/${currentYear}/edit`)
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create budget")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Budget Planning</h1>
          <p className="text-sm text-muted-foreground">Annual budgets and board-approved versions.</p>
        </div>
        <button
          type="button"
          onClick={createCurrentYearBudget}
          disabled={creating}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          <PlusCircle className="h-4 w-4" />
          Create Budget
        </button>
      </header>

      {loading ? <div className="h-36 animate-pulse rounded-xl bg-muted" /> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="space-y-4">
        {grouped.length === 0 && !loading ? (
          <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No budget versions yet for {currentYear}.
          </div>
        ) : null}
        {grouped.map(([year, versions]) => (
          <article key={year} className="rounded-xl border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">{year}</h2>
              <Link href={`/budget/${year}`} className="text-sm text-[hsl(var(--brand-primary))]">
                View
              </Link>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {versions.map((version) => (
                <div key={version.id} className="rounded-lg border border-border/60 bg-background px-3 py-2">
                  <p className="text-sm font-medium text-foreground">{version.version_name}</p>
                  <p className="text-xs text-muted-foreground">Version {version.version_number}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                      {version.status}
                    </span>
                    {version.is_board_approved ? (
                      <span className="rounded-full bg-[hsl(var(--brand-success)/0.2)] px-2 py-0.5 text-xs text-[hsl(var(--brand-success))]">
                        Board Approved
                      </span>
                    ) : null}
                    <span className="text-xs text-muted-foreground">
                      {version.line_item_count ?? 0} lines
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}

