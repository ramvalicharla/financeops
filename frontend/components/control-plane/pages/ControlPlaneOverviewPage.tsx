"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  listAirlockItems,
  listIntents,
  listJobs,
  listSnapshots,
  listTimeline,
} from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { PageScaffold } from "@/components/control-plane/PageScaffold"

function OverviewCard({
  title,
  href,
  content,
}: {
  title: string
  href?: string
  content: React.ReactNode
}) {
  const inner = (
    <article className="rounded-2xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      <div className="mt-3">{content}</div>
    </article>
  )

  return href ? <Link href={href}>{inner}</Link> : inner
}

export function ControlPlaneOverviewPage() {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const intentsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.intents({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    queryFn: () => listIntents({ entity_id: activeEntityId ?? undefined, limit: 25 }),
  })
  const jobsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    queryFn: () => listJobs({ entity_id: activeEntityId ?? undefined, limit: 25 }),
  })
  const timelineQuery = useQuery({
    queryKey: controlPlaneQueryKeys.timeline({ entity_id: activeEntityId ?? undefined, limit: 10 }),
    queryFn: () => listTimeline({ entity_id: activeEntityId ?? undefined, limit: 10 }),
  })
  const airlockQuery = useQuery({
    queryKey: controlPlaneQueryKeys.airlock({ entity_id: activeEntityId ?? undefined, limit: 25 }),
    queryFn: () => listAirlockItems({ entity_id: activeEntityId ?? undefined, limit: 25 }),
  })
  const snapshotsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.snapshots({ entity_id: activeEntityId ?? undefined, limit: 10 }),
    queryFn: () => listSnapshots({ entity_id: activeEntityId ?? undefined, limit: 10 }),
  })

  const openIntents = (intentsQuery.data ?? []).filter(
    (intent) => !["RECORDED", "REJECTED", "CANCELLED"].includes(intent.status),
  ).length
  const runningJobs = (jobsQuery.data ?? []).filter((job) =>
    ["QUEUED", "RUNNING", "STARTED"].includes(job.status),
  ).length
  const failedJobs = (jobsQuery.data ?? []).filter((job) =>
    ["FAILED", "ERROR"].includes(job.status),
  ).length
  const quarantinedArtifacts = (airlockQuery.data ?? []).filter(
    (item) => item.status === "QUARANTINED",
  ).length
  const latestTimelineEvent = timelineQuery.data?.[0]
  const latestSnapshot = snapshotsQuery.data?.[0]

  return (
    <PageScaffold
      title="Overview"
      description="A read-only decision cockpit composed from backend control-plane APIs. Each card reflects backend truth independently."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <OverviewCard
          title="Intent backlog"
          href="/control-plane/intents"
          content={
            intentsQuery.isError ? (
              <p className="text-sm text-muted-foreground">Intent backlog unavailable.</p>
            ) : (
              <>
                <p className="text-3xl font-semibold text-foreground">{openIntents}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Open intents returned by the backend.
                </p>
              </>
            )
          }
        />
        <OverviewCard
          title="Running jobs"
          href="/control-plane/jobs"
          content={
            jobsQuery.isError ? (
              <p className="text-sm text-muted-foreground">Job activity unavailable.</p>
            ) : (
              <>
                <p className="text-3xl font-semibold text-foreground">{runningJobs}</p>
                <p className="mt-2 text-sm text-muted-foreground">Queued or running governed jobs.</p>
              </>
            )
          }
        />
        <OverviewCard
          title="Failed jobs"
          href="/control-plane/jobs"
          content={
            jobsQuery.isError ? (
              <p className="text-sm text-muted-foreground">Failure count unavailable.</p>
            ) : (
              <>
                <p className="text-3xl font-semibold text-foreground">{failedJobs}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Failures visible from the backend job feed.
                </p>
              </>
            )
          }
        />
        <OverviewCard
          title="Airlock quarantine"
          href="/control-plane/airlock"
          content={
            airlockQuery.isError ? (
              <p className="text-sm text-muted-foreground">Airlock queue unavailable.</p>
            ) : (
              <>
                <p className="text-3xl font-semibold text-foreground">{quarantinedArtifacts}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Artifacts still quarantined by backend admission state.
                </p>
              </>
            )
          }
        />
        <OverviewCard
          title="Latest timeline event"
          href="/control-plane/timeline"
          content={
            timelineQuery.isError ? (
              <p className="text-sm text-muted-foreground">Timeline unavailable.</p>
            ) : latestTimelineEvent ? (
              <>
                <p className="text-base font-semibold text-foreground">
                  {latestTimelineEvent.timeline_type}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {latestTimelineEvent.occurred_at}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No timeline events were returned.</p>
            )
          }
        />
        <OverviewCard
          title="Latest snapshot"
          href="/control-plane/snapshots"
          content={
            snapshotsQuery.isError ? (
              <p className="text-sm text-muted-foreground">Snapshots unavailable.</p>
            ) : latestSnapshot ? (
              <>
                <p className="text-base font-semibold text-foreground">
                  {latestSnapshot.subject_type}:{latestSnapshot.subject_id}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Version {latestSnapshot.version_no} - hash{" "}
                  {latestSnapshot.determinism_hash.slice(0, 12)}...
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No snapshots were returned.</p>
            )
          }
        />
      </div>
    </PageScaffold>
  )
}
