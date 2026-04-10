"use client"

import { useMemo } from "react"
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
  const groups = useMemo(() => {
    const jobs = jobsQuery.data ?? []
    return {
      running: jobs.filter((job) => ["QUEUED", "RUNNING", "STARTED"].includes(job.status)),
      completed: jobs.filter((job) => ["SUCCEEDED", "COMPLETED", "RECORDED"].includes(job.status)),
      failed: jobs.filter((job) => ["FAILED", "ERROR"].includes(job.status)),
    }
  }, [jobsQuery.data])

  const renderGroup = (
    title: string,
    jobs: NonNullable<typeof jobsQuery.data>,
    emptyMessage: string,
  ) => (
    <section className="rounded-2xl border border-border bg-background p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
          {jobs.length}
        </span>
      </div>
      {!jobs.length ? (
        <p className="mt-3 text-sm text-muted-foreground">{emptyMessage}</p>
      ) : (
        <div className="mt-3 space-y-3">
          {jobs.map((job) => (
            <article key={job.job_id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-foreground">{job.job_type}</p>
                  <p className="font-mono text-xs text-muted-foreground">{job.job_id}</p>
                </div>
                <span className="rounded-full border border-border bg-background px-3 py-1 text-xs text-foreground">
                  {job.status}
                </span>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Intent</p>
                  <p className="mt-1 font-mono text-xs text-foreground">{job.intent_id}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Runner</p>
                  <p className="mt-1 text-sm text-foreground">{job.runner_type}</p>
                </div>
              </div>

              {job.error_message ? (
                <div className="mt-3 rounded-xl border border-[hsl(var(--brand-danger)/0.32)] bg-[hsl(var(--brand-danger)/0.08)] p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Error message</p>
                  <p className="mt-1 text-sm text-foreground">{job.error_message}</p>
                </div>
              ) : null}

              <div className="mt-3 flex items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!job.capabilities.retry.allowed}
                  aria-disabled={!job.capabilities.retry.allowed}
                >
                  {job.capabilities.retry.supported ? "Retry" : "Retry unavailable"}
                </Button>
                <p className="text-xs text-muted-foreground">
                  {job.capabilities.retry.reason ?? "Retry support is defined by the backend contract."}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )

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
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-24 animate-pulse rounded-2xl bg-muted/60" />
            ))}
          </div>
        ) : jobsQuery.error ? (
          <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
            <p className="font-medium text-foreground">Job activity failed to load</p>
            <p className="mt-1 text-muted-foreground">
              {jobsQuery.error instanceof Error ? jobsQuery.error.message : "The backend did not return jobs for the selected scope."}
            </p>
            <p className="mt-2 text-muted-foreground">Refresh the panel or reopen it from the shell.</p>
          </div>
        ) : !(jobsQuery.data?.length ?? 0) ? (
          <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            No data yet. Start by submitting a governed action so jobs appear here.
          </div>
        ) : (
          <div className="space-y-4">
            {renderGroup("Running jobs", groups.running, "No governed jobs are running right now.")}
            {renderGroup("Completed jobs", groups.completed, "No governed jobs have completed in this scope yet.")}
            {renderGroup("Failed jobs", groups.failed, "No governed jobs have failed in this scope.")}
          </div>
        )}
      </div>
    </Sheet>
  )
}
