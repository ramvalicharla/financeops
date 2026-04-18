"use client"

import { useCallback, useEffect, useState } from "react"
import { createMAWorkspace, getMAWorkspace, listMAWorkspaces } from "@/lib/api/ma"
import type { MAWorkspace } from "@/lib/types/ma"
import { WorkspaceCard } from "@/components/advisory/ma/WorkspaceCard"

interface WorkspaceMeta {
  ddCompletionPct: string
  memberCount: number
}

export default function MAWorkspaceListPage() {
  const [rows, setRows] = useState<MAWorkspace[]>([])
  const [meta, setMeta] = useState<Record<string, WorkspaceMeta>>({})
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const payload = await listMAWorkspaces({ limit: 50, offset: 0 })
      setRows(payload.data)
      const details = await Promise.all(
        payload.data.map(async (workspace) => {
          const detail = await getMAWorkspace(workspace.id)
          return [
            workspace.id,
            {
              ddCompletionPct: detail.dd_summary.completion_pct,
              memberCount: detail.members.length,
            },
          ] as const
        }),
      )
      setMeta(Object.fromEntries(details))
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load M&A workspaces")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const createNew = async () => {
    setCreating(true)
    setError(null)
    try {
      await createMAWorkspace({
        workspace_name: `M&A Workspace ${new Date().toISOString().slice(0, 10)}`,
        deal_codename: "Project Falcon",
        deal_type: "acquisition",
        target_company_name: "Target Company",
        indicative_deal_value: "500000000.00",
      })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create workspace")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">M&A Workspaces</h1>
          <p className="text-sm text-muted-foreground">1,000 credits per month</p>
        </div>
        <button
          type="button"
          onClick={createNew}
          disabled={creating}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
        >
          {creating ? "Creating..." : "New Workspace"}
        </button>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {rows.map((workspace) => (
          <WorkspaceCard
            key={workspace.id}
            workspace={workspace}
            ddCompletionPct={meta[workspace.id]?.ddCompletionPct ?? "0.00"}
            memberCount={meta[workspace.id]?.memberCount ?? 0}
          />
        ))}
        {rows.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No workspaces yet.
          </div>
        ) : null}
      </section>
    </div>
  )
}
