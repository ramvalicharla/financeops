"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJobs } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

export function ActivityTray() {
  const [expanded, setExpanded] = useState(false)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const jobsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    queryFn: () => listJobs({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    staleTime: 15_000,
  })

  const summary = useMemo(() => {
    const jobs = jobsQuery.data ?? []
    return {
      running: jobs.filter((job) => ["QUEUED", "RUNNING", "STARTED"].includes(job.status)),
      failed: jobs.filter((job) => ["FAILED", "ERROR"].includes(job.status)),
    }
  }, [jobsQuery.data])

  return (
    <div className="fixed bottom-0 left-0 right-0 z-20 border-t border-border bg-background/95 backdrop-blur md:left-64">
      <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-6">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-full border border-border bg-card px-3 py-1 text-foreground">
            Running {summary.running.length}
          </span>
          <span className="rounded-full border border-border bg-card px-3 py-1 text-foreground">
            Failed {summary.failed.length}
          </span>
          <span className="rounded-full border border-border bg-card px-3 py-1 text-muted-foreground">
            Retry state from backend job capability contract
          </span>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => setExpanded((open) => !open)}>
          {expanded ? "Hide activity" : "Show activity"}
        </Button>
      </div>
      {expanded ? (
        <div className="border-t border-border px-4 py-4 md:px-6">
          <div className="mx-auto grid w-full max-w-[1600px] gap-4 md:grid-cols-2">
            <section className="rounded-2xl border border-border bg-card p-4">
              <h3 className="text-sm font-semibold text-foreground">Running jobs</h3>
              {summary.running.length ? (
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  {summary.running.map((job) => (
                    <li key={job.job_id} className="rounded-xl border border-border bg-background px-3 py-3">
                      {job.job_type} - {job.status}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">No running jobs in the current scope.</p>
              )}
            </section>
            <section className="rounded-2xl border border-border bg-card p-4">
              <h3 className="text-sm font-semibold text-foreground">Failed jobs</h3>
              {summary.failed.length ? (
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  {summary.failed.map((job) => (
                    <li key={job.job_id} className="rounded-xl border border-border bg-background px-3 py-3">
                      {job.job_type} - {job.error_message ?? "Backend reported failure"}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">No failed jobs in the current scope.</p>
              )}
            </section>
          </div>
        </div>
      ) : null}
    </div>
  )
}
