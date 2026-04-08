"use client"

import { useQuery } from "@tanstack/react-query"
import { listJobs } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"

export function JobPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedJobId = useControlPlaneStore((state) => state.selected_job_id)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const jobsQuery = useQuery({
    queryKey: ["control-plane-jobs", activeEntityId],
    queryFn: async () => listJobs({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    enabled: activePanel === "jobs",
  })

  return (
    <Sheet
      open={activePanel === "jobs"}
      onClose={closePanel}
      title="Job Panel"
      description="Running, completed, and failed governed jobs."
      width="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {selectedJobId ? `Focused job: ${selectedJobId}` : "Latest job activity for current scope."}
          </p>
          <Button type="button" variant="outline" onClick={() => void jobsQuery.refetch()}>
            Refresh Jobs
          </Button>
        </div>
        {jobsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading jobs...</p>
        ) : jobsQuery.error ? (
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load jobs.</p>
        ) : !(jobsQuery.data?.length ?? 0) ? (
          <p className="text-sm text-muted-foreground">No jobs in the current scope.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Job ID</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Intent</th>
                  <th className="px-4 py-2">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(jobsQuery.data ?? []).map((job) => (
                  <tr key={job.job_id}>
                    <td className="px-4 py-2 font-mono text-xs text-foreground">{job.job_id}</td>
                    <td className="px-4 py-2 text-foreground">{job.job_type}</td>
                    <td className="px-4 py-2 text-foreground">{job.status}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{job.intent_id}</td>
                    <td className="px-4 py-2 text-muted-foreground">{job.error_message ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Sheet>
  )
}
