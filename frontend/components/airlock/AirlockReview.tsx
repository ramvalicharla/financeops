"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { admitAirlockItem, getAirlockItem, rejectAirlockItem } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { StructuredDataView } from "@/components/ui"
import { Button } from "@/components/ui/button"

interface AirlockReviewProps {
  itemId: string
}

export function AirlockReview({ itemId }: AirlockReviewProps) {
  const queryClient = useQueryClient()
  const [rejectReason, setRejectReason] = useState("")
  const itemQuery = useQuery({
    queryKey: controlPlaneQueryKeys.airlockItem(itemId),
    queryFn: async () => getAirlockItem(itemId),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: controlPlaneQueryKeys.airlockRoot() })
    await queryClient.invalidateQueries({ queryKey: controlPlaneQueryKeys.airlockItem(itemId) })
  }

  const admitMutation = useMutation({
    mutationFn: async () => admitAirlockItem(itemId),
    onSuccess: refresh,
  })
  const rejectMutation = useMutation({
    mutationFn: async () => rejectAirlockItem(itemId, rejectReason || "Rejected from UI review."),
    onSuccess: refresh,
  })
  const flowSteps = useMemo<FlowStripStep[]>(() => {
    const status = itemQuery.data?.status
    return [
      { label: "Upload", tone: status ? "success" : "default" },
      { label: "Airlock", tone: status ? "active" : "default" },
      { label: "Review", tone: status === "QUARANTINED" ? "warning" : "default" },
      { label: "Admit / Reject", tone: status === "ADMITTED" || status === "REJECTED" ? "success" : "default" },
      { label: "Process", tone: status === "ADMITTED" ? "active" : "default" },
    ]
  }, [itemQuery.data?.status])

  if (itemQuery.isLoading) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Upload Flow"
          subtitle="Review validation output, then use backend admission actions only."
          steps={flowSteps}
        />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-2xl bg-muted/60" />
          ))}
        </div>
      </div>
    )
  }

  if (itemQuery.error || !itemQuery.data) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Upload Flow"
          subtitle="Review validation output, then use backend admission actions only."
          steps={flowSteps}
        />
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Review data failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {itemQuery.error instanceof Error ? itemQuery.error.message : "The backend did not return the requested airlock item."}
          </p>
          <p className="mt-2 text-muted-foreground">Return to the queue and reopen the item.</p>
        </div>
      </div>
    )
  }

  const item = itemQuery.data

  return (
    <div className="space-y-4">
      <FlowStrip
        title="Upload Flow"
        subtitle="Review validation output, then use backend admission actions only."
        steps={flowSteps}
      />

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
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Origin</p>
          <p className="mt-1 text-foreground">
            {item.metadata?.source === "onboarding"
              ? `Onboarding${typeof item.metadata.onboarding_step === "string" ? ` (${item.metadata.onboarding_step})` : ""}`
              : "Derived from backend state"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Received</p>
          <p className="mt-1 text-foreground">{item.submitted_at ?? "-"}</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Availability</p>
        <p className="mt-2 text-sm text-foreground">
          {item.status === "ADMITTED"
            ? "Confirmed by backend admission. Downstream processing may use this item."
            : "Not admitted yet. Downstream processing should not treat this item as usable."}
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Metadata</p>
        <div className="mt-2">
          <StructuredDataView
            data={item.metadata ?? null}
            emptyMessage="No metadata was returned for this airlock item."
            compact
          />
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Validation issues</p>
        {item.findings.length ? (
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {item.findings.map((finding, index) => (
              <li key={`${item.airlock_item_id}-${index}`} className="rounded-xl border border-border bg-muted/30 px-3 py-3">
                <StructuredDataView
                  data={finding}
                  emptyMessage="No structured finding details were returned."
                  compact
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            No validation issues were returned for this item. It is ready for review.
          </p>
        )}
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
        <p className="text-xs text-muted-foreground">
          These buttons call the backend admit and reject APIs directly. The UI keeps rendering the backend-returned item state after refresh.
        </p>
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
