"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJobs } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { JobBody } from "@/components/control-plane/bodies/JobBody"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { Button } from "@/components/ui/button"

interface ControlPlaneJobsPageProps {
  jobId?: string | null
}

export function ControlPlaneJobsPage({ jobId }: ControlPlaneJobsPageProps) {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(jobId ?? null)
  const jobsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({ entity_id: activeEntityId ?? undefined, limit: 50 }),
    queryFn: () => listJobs({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })

  const rows = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data])
  const resolvedJobId = jobId ?? selectedJobId ?? rows[0]?.job_id ?? null
  const summary = useMemo(
    () => ({
      running: rows.filter((job) => ["QUEUED", "RUNNING", "STARTED"].includes(job.status)).length,
      failed: rows.filter((job) => ["FAILED", "ERROR"].includes(job.status)).length,
    }),
    [rows],
  )

  return (
    <PageScaffold
      title="Jobs"
      description="Execution visibility for backend-governed jobs, including status, retry capability, and error surfaces."
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Job list</h2>
              <p className="text-sm text-muted-foreground">
                {summary.running} running - {summary.failed} failed
              </p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => void jobsQuery.refetch()}>
              Refresh
            </Button>
          </div>
          {jobsQuery.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading jobs...</p>
          ) : !rows.length ? (
            <p className="mt-4 text-sm text-muted-foreground">No jobs were returned for this scope.</p>
          ) : (
            <div className="mt-4 space-y-2">
              {rows.map((job) => {
                const isActive = resolvedJobId === job.job_id
                return (
                  <article
                    key={job.job_id}
                    className={`rounded-xl border p-3 ${isActive ? "border-foreground bg-background" : "border-border bg-background/60"}`}
                  >
                    <button type="button" className="w-full text-left" onClick={() => setSelectedJobId(job.job_id)}>
                      <p className="text-sm font-semibold text-foreground">{job.job_type}</p>
                      <p className="mt-1 font-mono text-xs text-muted-foreground">{job.job_id}</p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {job.status} - {job.runner_type} - intent {job.intent_id}
                      </p>
                    </button>
                    <Link
                      href={`/control-plane/jobs/${job.job_id}`}
                      className="mt-3 inline-block text-xs font-medium text-foreground underline underline-offset-4"
                    >
                      Open full page
                    </Link>
                  </article>
                )
              })}
            </div>
          )}
        </section>
        <section className="rounded-2xl border border-border bg-card p-4">
          <JobBody jobId={resolvedJobId} entityId={activeEntityId} showRefreshButton={false} />
        </section>
      </div>
    </PageScaffold>
  )
}
