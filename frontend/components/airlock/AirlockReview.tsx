"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { admitAirlockItem, getAirlockItem, rejectAirlockItem } from "@/lib/api/control-plane"
import { Button } from "@/components/ui/button"

interface AirlockReviewProps {
  itemId: string
}

export function AirlockReview({ itemId }: AirlockReviewProps) {
  const queryClient = useQueryClient()
  const [rejectReason, setRejectReason] = useState("")
  const itemQuery = useQuery({
    queryKey: ["control-plane-airlock-item", itemId],
    queryFn: async () => getAirlockItem(itemId),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["control-plane-airlock"] })
    await queryClient.invalidateQueries({ queryKey: ["control-plane-airlock-item", itemId] })
  }

  const admitMutation = useMutation({
    mutationFn: async () => admitAirlockItem(itemId),
    onSuccess: refresh,
  })
  const rejectMutation = useMutation({
    mutationFn: async () => rejectAirlockItem(itemId, rejectReason || "Rejected from UI review."),
    onSuccess: refresh,
  })

  if (itemQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading airlock review...</p>
  }

  if (itemQuery.error || !itemQuery.data) {
    return <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load airlock item.</p>
  }

  const item = itemQuery.data

  return (
    <div className="space-y-4">
      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Airlock Item</p>
          <p className="mt-1 break-all font-mono text-foreground">{item.airlock_item_id}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
          <p className="mt-1 text-foreground">{item.status}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Source Type</p>
          <p className="mt-1 text-foreground">{item.source_type}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Received</p>
          <p className="mt-1 text-foreground">{item.submitted_at ?? "-"}</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Metadata</p>
        <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
          {JSON.stringify(item.metadata ?? {}, null, 2)}
        </pre>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Findings</p>
        <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
          {JSON.stringify(item.findings ?? [], null, 2)}
        </pre>
      </section>

      <section className="space-y-3 rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Review Actions</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            onClick={() => admitMutation.mutate()}
            disabled={admitMutation.isPending || item.status === "ADMITTED"}
          >
            Admit
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => rejectMutation.mutate()}
            disabled={rejectMutation.isPending || item.status === "ADMITTED"}
          >
            Reject
          </Button>
          <Button type="button" variant="outline" onClick={() => void itemQuery.refetch()}>
            Refresh
          </Button>
        </div>
        <label className="block space-y-2 text-sm">
          <span className="text-muted-foreground">Reject reason</span>
          <textarea
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            placeholder="Optional reason passed to backend reject API"
          />
        </label>
      </section>
    </div>
  )
}
