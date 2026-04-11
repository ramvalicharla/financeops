"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { listAirlockItems } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

interface AirlockQueueProps {
  detailHrefPrefix?: string
}

export function AirlockQueue({ detailHrefPrefix = "/settings/airlock" }: AirlockQueueProps) {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const airlockQuery = useQuery({
    queryKey: controlPlaneQueryKeys.airlock({ entity_id: activeEntityId ?? undefined, limit: 50 }),
    queryFn: async () => listAirlockItems({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })
  const queueSteps = useMemo<FlowStripStep[]>(() => {
    const items = airlockQuery.data ?? []
    const hasItems = items.length > 0
    const hasQuarantined = items.some((item) => item.status === "QUARANTINED")
    const hasAdmitted = items.some((item) => item.status === "ADMITTED")
    const hasRejected = items.some((item) => item.status === "REJECTED")

    return [
      { label: "Upload", tone: hasItems ? "success" : "active" },
      { label: "Airlock", tone: hasItems ? "active" : "default" },
      { label: "Review", tone: hasQuarantined || hasRejected ? "warning" : "default" },
      { label: "Admit", tone: hasAdmitted ? "success" : "default" },
      { label: "Process", tone: hasAdmitted ? "active" : "default" },
    ]
  }, [airlockQuery.data])

  if (airlockQuery.isLoading) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Upload Flow"
          subtitle="Upload, review, admit, and process through the backend-returned intake path."
          steps={queueSteps}
        />
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-2xl bg-muted/60" />
          ))}
        </div>
      </div>
    )
  }

  if (airlockQuery.error) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Upload Flow"
          subtitle="Upload, review, admit, and process through the backend-returned intake path."
          steps={queueSteps}
        />
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Airlock queue failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {airlockQuery.error instanceof Error ? airlockQuery.error.message : "The backend did not return queue items."}
          </p>
          <p className="mt-2 text-muted-foreground">Try refreshing the page or reopening the current entity scope.</p>
        </div>
      </div>
    )
  }

  if (!(airlockQuery.data?.length ?? 0)) {
    return (
      <div className="space-y-4">
        <FlowStrip
          title="Upload Flow"
          subtitle="Upload, review, admit, and process through the backend-returned intake path."
          steps={queueSteps}
        />
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          No data yet. Start by creating an upload so it appears in the airlock queue for review.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <FlowStrip
        title="Upload Flow"
        subtitle="Upload, review, admit, and process through the backend-returned intake path."
        steps={queueSteps}
      />
      <div className="space-y-3">
        {(airlockQuery.data ?? []).map((item) => (
          <article key={item.airlock_item_id} className="rounded-2xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-xs text-muted-foreground">{item.airlock_item_id}</p>
                <p className="mt-1 text-sm font-semibold text-foreground">
                  {item.file_name ?? item.source_reference ?? item.source_type}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {item.source_type} - received {item.submitted_at ?? "unknown"}
                </p>
                {item.metadata?.source === "onboarding" ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Origin: onboarding
                    {typeof item.metadata.onboarding_step === "string"
                      ? ` (${item.metadata.onboarding_step})`
                      : ""}
                  </p>
                ) : null}
              </div>
              <span className="rounded-full border border-border bg-background px-3 py-1 text-xs text-foreground">
                {item.status}
              </span>
            </div>

            <p className="mt-3 text-xs text-muted-foreground">
              {item.status === "ADMITTED"
                ? "Backend confirms this item has been admitted."
                : "This item is not usable until the backend confirms admission."}
            </p>

            <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
              <div className="rounded-xl border border-border bg-background/70 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Validation issues</p>
                {item.findings.length ? (
                  <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                    {item.findings.map((finding, index) => (
                      <li key={`${item.airlock_item_id}-${index}`}>{JSON.stringify(finding)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">No validation issues reported yet.</p>
                )}
              </div>
              <div className="flex items-end">
                <Link className="text-sm font-medium text-foreground underline underline-offset-4" href={`${detailHrefPrefix}/${item.airlock_item_id}`}>
                  Open review
                </Link>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
