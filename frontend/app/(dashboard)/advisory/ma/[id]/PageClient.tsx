"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { DDTracker } from "@/components/advisory/ma/DDTracker"
import { getMADDTracker, getMAWorkspace, updateMADDItem } from "@/lib/api/ma"
import type { MADDItem, MADDTrackerSummary, MAWorkspace, MAWorkspaceMember } from "@/lib/types/ma"

export default function MAWorkspaceDetailPage() {
  const params = useParams()
  const workspaceId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [workspace, setWorkspace] = useState<MAWorkspace | null>(null)
  const [members, setMembers] = useState<MAWorkspaceMember[]>([])
  const [summary, setSummary] = useState<MADDTrackerSummary | null>(null)
  const [items, setItems] = useState<MADDItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const detail = await getMAWorkspace(workspaceId)
      const dd = await getMADDTracker(workspaceId)
      setWorkspace(detail.workspace)
      setMembers(detail.members)
      setSummary(dd.summary)
      setItems(dd.items)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load workspace")
    }
  }, [workspaceId])

  useEffect(() => {
    if (workspaceId) {
      void load()
    }
  }, [workspaceId, load])

  const handleStatusChange = async (itemId: string, status: string) => {
    await updateMADDItem(workspaceId, itemId, { status })
    await load()
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{workspace?.deal_codename ?? "Workspace"}</h1>
          <p className="text-sm text-muted-foreground">{workspace?.target_company_name ?? ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/advisory/ma/${workspaceId}/valuation`} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            Valuation
          </Link>
          <Link href={`/advisory/ma/${workspaceId}/documents`} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            Documents
          </Link>
        </div>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Overview</h2>
        <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          <p className="text-muted-foreground">Deal Type: <span className="text-foreground">{workspace?.deal_type ?? "-"}</span></p>
          <p className="text-muted-foreground">Status: <span className="text-foreground">{workspace?.deal_status ?? "-"}</span></p>
          <p className="text-muted-foreground">Members: <span className="text-foreground">{members.length}</span></p>
          <p className="text-muted-foreground">DD Completion: <span className="text-foreground">{summary?.completion_pct ?? "0.00"}%</span></p>
        </div>
      </section>

      {summary ? <DDTracker summary={summary} items={items} onStatusChange={handleStatusChange} /> : null}
    </div>
  )
}
