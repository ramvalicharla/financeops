"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { listJobs, type ControlPlaneJob } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { GuardFailureCard, StateBadge } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface JobBodyProps {
  jobId?: string | null
  entityId?: string | null
  showRefreshButton?: boolean
}

type JobTab = "overview" | "execution" | "audit"

const JOB_TABS: Array<{ id: JobTab; label: string; description: string }> = [
  { id: "overview", label: "Overview", description: "Scope and state" },
  { id: "execution", label: "Execution", description: "Live and completed work" },
  { id: "audit", label: "Audit", description: "Errors and retry support" },
]

const QUEUED_STATUSES = ["QUEUED", "PENDING", "SCHEDULED"]
const RUNNING_STATUSES = ["RUNNING", "STARTED", "PROCESSING"]
const COMPLETED_STATUSES = ["SUCCEEDED", "COMPLETED", "RECORDED", "POSTED"]
const FAILED_STATUSES = ["FAILED", "ERROR", "REJECTED"]

const formatDateTime = (value: string | null | undefined): string => {
  if (!value) {
    return "-"
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const formatDuration = (startedAt: string | null | undefined, endAt: string | null | undefined, nowMs: number): string => {
  if (!startedAt) {
    return "-"
  }
  const startMs = Date.parse(startedAt)
  if (Number.isNaN(startMs)) {
    return "-"
  }

  const finishMs = endAt ? Date.parse(endAt) : nowMs
  if (Number.isNaN(finishMs)) {
    return "-"
  }

  const diff = Math.max(finishMs - startMs, 0)
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  }
  return `${seconds}s`
}

function TabButton({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-left text-xs transition-colors",
        active
          ? "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.1)] text-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      {label}
    </button>
  )
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words font-medium text-foreground">{value}</p>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

function SectionCard({
  title,
  eyebrow,
  children,
}: {
  title: string
  eyebrow: string
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{eyebrow}</p>
      <h3 className="mt-1 text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function CapabilityBadge({
  supported,
  allowed,
}: {
  supported: boolean
  allowed: boolean
}) {
  const tone = supported && allowed
    ? "bg-[hsl(var(--brand-success)/0.14)] text-[hsl(var(--brand-success))]"
    : supported
      ? "bg-[hsl(var(--brand-warning)/0.14)] text-[hsl(var(--brand-warning))]"
      : "bg-muted text-muted-foreground"

  return (
    <span className={cn("rounded-full px-3 py-1 text-xs font-medium", tone)}>
      {supported ? (allowed ? "Retry available" : "Retry gated") : "Retry unavailable"}
    </span>
  )
}

function JobCard({
  job,
  focused,
  nowMs,
  onOpenEvidence,
}: {
  job: ControlPlaneJob
  focused: boolean
  nowMs: number
  onOpenEvidence: (jobId: string) => void
}) {
  const duration = formatDuration(job.started_at, job.finished_at ?? job.failed_at, nowMs)

  return (
    <article
      className={cn(
        "rounded-xl border p-4 transition-colors",
        focused
          ? "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.08)]"
          : "border-border bg-card",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">{job.job_type}</p>
          <p className="font-mono text-xs text-muted-foreground">{job.job_id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge status={job.status} label={`${job.status} status`} />
          <CapabilityBadge supported={job.capabilities.retry.supported} allowed={job.capabilities.retry.allowed} />
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Intent" value={job.intent_id} />
        <MetricCard label="Runner" value={job.runner_type} detail={job.queue_name} />
        <MetricCard
          label="Duration"
          value={duration}
          detail={job.started_at ? `Started ${formatDateTime(job.started_at)}` : "Not started"}
        />
        <MetricCard
          label="Completion"
          value={job.finished_at ?? job.failed_at ? formatDateTime(job.finished_at ?? job.failed_at) : "Running"}
          detail={job.retry_count > 0 ? `${job.retry_count} retry attempt(s)` : "No retries yet"}
        />
      </div>

      {job.error_message ? (
        <div className="mt-3 rounded-xl border border-[hsl(var(--brand-danger)/0.32)] bg-[hsl(var(--brand-danger)/0.08)] p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Error message</p>
          <p className="mt-1 text-sm text-foreground">{job.error_message}</p>
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!job.capabilities.retry.allowed}
          aria-disabled={!job.capabilities.retry.allowed}
        >
          {job.capabilities.retry.supported ? "Retry" : "Retry unavailable"}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onOpenEvidence(job.job_id)}>
          Open Evidence
        </Button>
        <p className="text-xs text-muted-foreground">
          {job.capabilities.retry.reason ?? "Retry support is defined by the backend contract."}
        </p>
      </div>
    </article>
  )
}

export function JobBody({ jobId, entityId, showRefreshButton = true }: JobBodyProps) {
  const selectedJobId = useControlPlaneStore((state) => state.selected_job_id)
  const openEvidenceDrawer = useControlPlaneStore((state) => state.openEvidenceDrawer)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const [activeTab, setActiveTab] = useState<JobTab>("overview")
  const [nowMs, setNowMs] = useState(() => Date.now())
  const resolvedJobId = jobId ?? selectedJobId
  const resolvedEntityId = entityId ?? activeEntityId

  useEffect(() => {
    const interval = window.setInterval(() => setNowMs(Date.now()), 15000)
    return () => window.clearInterval(interval)
  }, [])

  const jobsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({ entity_id: resolvedEntityId ?? undefined, limit: 100 }),
    queryFn: async () => listJobs({ entity_id: resolvedEntityId ?? undefined, limit: 100 }),
  })

  const groups = useMemo(() => {
    const jobs = jobsQuery.data ?? []
    return {
      queued: jobs.filter((job) => QUEUED_STATUSES.includes(job.status)),
      running: jobs.filter((job) => RUNNING_STATUSES.includes(job.status)),
      completed: jobs.filter((job) => COMPLETED_STATUSES.includes(job.status)),
      failed: jobs.filter((job) => FAILED_STATUSES.includes(job.status)),
    }
  }, [jobsQuery.data])

  if (jobsQuery.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded-2xl bg-muted/60" />
        ))}
      </div>
    )
  }

  if (jobsQuery.error) {
    return (
      <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
        <p className="font-medium text-foreground">Job activity failed to load</p>
        <p className="mt-1 text-muted-foreground">
          {jobsQuery.error instanceof Error
            ? jobsQuery.error.message
            : "The backend did not return jobs for the selected scope."}
        </p>
      </div>
    )
  }

  if (!(jobsQuery.data?.length ?? 0)) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        No data yet. Start by submitting a governed action so jobs appear here.
      </div>
    )
  }

  const focusedJob =
    jobsQuery.data?.find((job) => job.job_id === resolvedJobId) ??
    groups.running[0] ??
    groups.queued[0] ??
    groups.failed[0] ??
    groups.completed[0] ??
    null

  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Queued" value={String(groups.queued.length)} detail="Waiting for execution" />
        <MetricCard label="Running" value={String(groups.running.length)} detail="Currently active jobs" />
        <MetricCard label="Completed" value={String(groups.completed.length)} detail="Terminal success states" />
        <MetricCard label="Failed" value={String(groups.failed.length)} detail="Terminal error states" />
      </div>

      <div className="flex flex-wrap gap-2">
        {JOB_TABS.map((tab) => (
          <TabButton key={tab.id} active={activeTab === tab.id} label={tab.label} onClick={() => setActiveTab(tab.id)} />
        ))}
      </div>

      {activeTab === "overview" ? (
        <div className="space-y-4">
          <SectionCard title="Execution Scope" eyebrow="Jobs">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Entity" value={resolvedEntityId ?? "All entities"} />
              <MetricCard label="Focused job" value={resolvedJobId ?? "None selected"} />
              <MetricCard label="Latest job status" value={focusedJob?.status ?? "No focused job"} />
              <MetricCard
                label="Retry support"
                value={focusedJob ? (focusedJob.capabilities.retry.supported ? "Available" : "Unavailable") : "Not selected"}
                detail="Backend capability governs retry availability."
              />
            </div>
          </SectionCard>

          <SectionCard title="Focused Job" eyebrow="Execution">
            {focusedJob ? (
              <JobCard job={focusedJob} focused nowMs={nowMs} onOpenEvidence={(id) => openEvidenceDrawer("job", id)} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a job to inspect its execution timing and backend capabilities.
              </p>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "execution" ? (
        <div className="space-y-4">
          <SectionCard title="Queued Jobs" eyebrow="Execution">
            {groups.queued.length ? (
              <div className="space-y-3">
                {groups.queued.map((job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    focused={resolvedJobId === job.job_id}
                    nowMs={nowMs}
                    onOpenEvidence={(id) => openEvidenceDrawer("job", id)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No governed jobs are queued right now.</p>
            )}
          </SectionCard>

          <SectionCard title="Running Jobs" eyebrow="Execution">
            {groups.running.length ? (
              <div className="space-y-3">
                {groups.running.map((job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    focused={resolvedJobId === job.job_id}
                    nowMs={nowMs}
                    onOpenEvidence={(id) => openEvidenceDrawer("job", id)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No governed jobs are running right now.</p>
            )}
          </SectionCard>

          <SectionCard title="Completed Jobs" eyebrow="Execution">
            {groups.completed.length ? (
              <div className="space-y-3">
                {groups.completed.map((job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    focused={resolvedJobId === job.job_id}
                    nowMs={nowMs}
                    onOpenEvidence={(id) => openEvidenceDrawer("job", id)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No governed jobs have completed in this scope yet.</p>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "audit" ? (
        <div className="space-y-4">
          <SectionCard title="Failed Jobs and Recoverability" eyebrow="Audit">
            {groups.failed.length ? (
              <div className="space-y-3">
                {groups.failed.map((job) => (
                  <div key={job.job_id} className="rounded-xl border border-border bg-card p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-foreground">{job.job_type}</p>
                        <p className="font-mono text-xs text-muted-foreground">{job.job_id}</p>
                      </div>
                      <StateBadge status={job.status} label={`${job.status} status`} />
                    </div>

                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <MetricCard label="Failure at" value={formatDateTime(job.failed_at)} detail={job.error_code ?? "No error code"} />
                      <MetricCard label="Retry count" value={`${job.retry_count} / ${job.max_retries}`} detail="Backend-defined retry budget" />
                    </div>

                    {job.error_message ? (
                      <div className="mt-3 rounded-xl border border-[hsl(var(--brand-danger)/0.28)] bg-[hsl(var(--brand-danger)/0.08)] p-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Error message</p>
                        <p className="mt-1 text-sm text-foreground">{job.error_message}</p>
                      </div>
                    ) : null}

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={!job.capabilities.retry.allowed}
                        aria-disabled={!job.capabilities.retry.allowed}
                      >
                        {job.capabilities.retry.supported ? "Retry" : "Retry unavailable"}
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => openEvidenceDrawer("job", job.job_id)}>
                        Open Evidence
                      </Button>
                      <p className="text-xs text-muted-foreground">
                        Backend retry policy applies to failed jobs in this panel.
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No governed jobs have failed in this scope.</p>
            )}
          </SectionCard>

          <SectionCard title="Capability Notes" eyebrow="Audit">
            <GuardFailureCard
              title="Execution telemetry is partial"
              message="Progress percentage and ETA are not exposed by the current backend contract."
              recommendation="Use duration, retry capability, and terminal timestamps for operator decisions until richer job telemetry is available."
              tone="warning"
            />
          </SectionCard>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {resolvedJobId ? `Focused job: ${resolvedJobId}` : "Latest job activity for the current scope."}
        </p>
        <div className="flex flex-wrap gap-2">
          {showRefreshButton ? (
            <Button type="button" variant="outline" onClick={() => void jobsQuery.refetch()}>
              Refresh Jobs
            </Button>
          ) : null}
          {focusedJob ? (
            <Button type="button" variant="outline" onClick={() => openEvidenceDrawer("job", focusedJob.job_id)}>
              Open Focused Evidence
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
