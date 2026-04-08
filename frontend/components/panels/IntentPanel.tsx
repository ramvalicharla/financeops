"use client"

import { useQuery } from "@tanstack/react-query"
import { getIntent } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"

export function IntentPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedIntentId = useControlPlaneStore((state) => state.selected_intent_id)
  const intentPayload = useControlPlaneStore((state) => state.intent_payload)

  const intentQuery = useQuery({
    queryKey: ["control-plane-intent", selectedIntentId],
    queryFn: async () => (selectedIntentId ? getIntent(selectedIntentId) : null),
    enabled: activePanel === "intent" && Boolean(selectedIntentId),
  })

  const intent = intentQuery.data ?? intentPayload
  const guardResults =
    intent && "guard_results" in intent ? intent.guard_results : intentPayload?.guard_results

  return (
    <Sheet
      open={activePanel === "intent"}
      onClose={closePanel}
      title="Intent Panel"
      description="Backend-governed lifecycle details for the latest mutation."
      width="max-w-xl"
    >
      {!intent ? (
        <p className="text-sm text-muted-foreground">No governed intent selected.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="grid gap-3 rounded-xl border border-border bg-background p-4 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Intent ID</p>
              <p className="mt-1 break-all font-mono text-foreground">{intent.intent_id}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
              <p className="mt-1 text-foreground">{intent.status}</p>
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

          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Record References</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(intent.record_refs ?? {}, null, 2)}
            </pre>
          </div>

          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Guard Summary</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(guardResults ?? {}, null, 2)}
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
