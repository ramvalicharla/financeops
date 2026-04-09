"use client"

import { useQuery } from "@tanstack/react-query"
import { getDeterminism } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"

export function DeterminismPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedSubjectType = useControlPlaneStore((state) => state.selected_subject_type)
  const selectedSubjectId = useControlPlaneStore((state) => state.selected_subject_id)

  const query = useQuery({
    queryKey: ["control-plane-determinism", selectedSubjectType, selectedSubjectId],
    queryFn: async () => getDeterminism(selectedSubjectType ?? "", selectedSubjectId ?? ""),
    enabled: activePanel === "determinism" && Boolean(selectedSubjectType) && Boolean(selectedSubjectId),
  })

  return (
    <Sheet
      open={activePanel === "determinism"}
      onClose={closePanel}
      title="Determinism Panel"
      description="Replayability, hashes, snapshots, and input evidence for the selected subject."
      width="max-w-3xl"
    >
      {!selectedSubjectType || !selectedSubjectId ? (
        <p className="text-sm text-muted-foreground">Select a snapshot-backed subject to inspect determinism.</p>
      ) : query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading determinism evidence...</p>
      ) : query.error || !query.data ? (
        <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load determinism evidence.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="grid gap-3 rounded-xl border border-border bg-background p-4 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Hash</p>
              <p className="mt-1 break-all font-mono text-foreground">{query.data.determinism_hash}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Snapshot Version</p>
              <p className="mt-1 text-foreground">{query.data.version_no}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Replay Supported</p>
              <p className="mt-1 text-foreground">{query.data.replay_supported ? "Yes" : "No"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Trigger</p>
              <p className="mt-1 text-foreground">{query.data.trigger_event ?? "-"}</p>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Replay Result</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(query.data.replay ?? {}, null, 2)}
            </pre>
          </div>

          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Inputs</p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(query.data.inputs ?? [], null, 2)}
            </pre>
          </div>

          <Button type="button" variant="outline" onClick={() => void query.refetch()}>
            Refresh Determinism
          </Button>
        </div>
      )}
    </Sheet>
  )
}
