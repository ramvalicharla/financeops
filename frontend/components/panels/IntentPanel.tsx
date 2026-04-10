"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getIntent, type ControlPlaneIntent } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"

export function IntentPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedIntentId = useControlPlaneStore((state) => state.selected_intent_id)

  const intentQuery = useQuery({
    queryKey: ["control-plane-intent", selectedIntentId],
    queryFn: async () => (selectedIntentId ? getIntent(selectedIntentId) : null),
    enabled: activePanel === "intent" && Boolean(selectedIntentId),
  })

  const intent = intentQuery.data
  const guardResults = intent?.guard_results
  const events: NonNullable<ControlPlaneIntent["events"]> =
    intent && "events" in intent && Array.isArray(intent.events) ? intent.events : []
  const validationRows = useMemo(() => {
    if (!guardResults) {
      return []
    }
    return Object.entries(guardResults).filter(([key]) => key !== "overall_passed")
  }, [guardResults])

  return (
    <Sheet
      open={activePanel === "intent"}
      onClose={closePanel}
      title="Intent Panel"
      description="Backend-returned intent details for the selected governed action."
      width="max-w-xl"
    >
      {intentQuery.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-2xl bg-muted/60" />
          ))}
        </div>
      ) : !selectedIntentId ? (
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          No data yet. Open an intent from a backend-confirmed action to inspect it here.
        </div>
      ) : intentQuery.error ? (
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Intent details failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {intentQuery.error instanceof Error ? intentQuery.error.message : "The backend did not return the selected intent."}
          </p>
          <p className="mt-2 text-muted-foreground">Refresh the panel or reopen it from the originating action.</p>
        </div>
      ) : !intent ? (
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          No backend intent data was returned for the selected identifier.
        </div>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="grid gap-3 rounded-2xl border border-border bg-background p-4 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Intent ID</p>
              <p className="mt-1 break-all font-mono text-foreground">{intent.intent_id}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
              <p className="mt-1">
                <span className="rounded-full border border-border bg-card px-3 py-1 text-foreground">
                  {intent.status}
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Job ID</p>
              <p className="mt-1 break-all font-mono text-foreground">{intent.job_id ?? "-"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Next Action</p>
              <p className="mt-1 text-foreground">{intent.next_action ?? "-"}</p>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-background p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Validation Results</p>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  guardResults?.overall_passed
                    ? "bg-[hsl(var(--brand-success)/0.14)] text-[hsl(var(--brand-success))]"
                    : "bg-[hsl(var(--brand-danger)/0.12)] text-[hsl(var(--brand-danger))]"
                }`}
              >
                {guardResults?.overall_passed ? "Pass" : "Check results"}
              </span>
            </div>
            {validationRows.length ? (
              <div className="mt-3 space-y-2">
                {validationRows.map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between rounded-xl border border-border bg-card px-3 py-3">
                    <span className="text-sm text-foreground">{key}</span>
                    <span className="text-xs text-muted-foreground">{JSON.stringify(value)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No step-level validation details were returned for this intent.
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Approval Chain</p>
            {events.length ? (
              <div className="mt-3 space-y-2">
                {events.map((event) => (
                  <div key={event.event_id} className="rounded-xl border border-border bg-card px-3 py-3">
                    <p className="text-sm font-medium text-foreground">{event.event_type}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {event.actor_role ?? "system"} · {event.actor_user_id ?? "unknown"} · {event.event_at ?? "unknown time"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No approval-chain events were returned for this intent yet.
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Record References</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(intent.record_refs ?? {}, null, 2)}
            </pre>
          </div>

          <div className="rounded-2xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Intent JSON</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(intent.payload ?? {}, null, 2)}
            </pre>
          </div>

          <Button
            type="button"
            variant="outline"
            onClick={() => {
              void intentQuery.refetch()
            }}
          >
            Refresh Intent
          </Button>
        </div>
      )}
    </Sheet>
  )
}
