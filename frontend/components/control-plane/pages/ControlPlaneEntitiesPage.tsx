"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  getControlPlaneEntity,
  listControlPlaneEntities,
  listIntents,
  listJobs,
} from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { Button } from "@/components/ui/button"

interface ControlPlaneEntitiesPageProps {
  entityId?: string | null
}

export function ControlPlaneEntitiesPage({ entityId }: ControlPlaneEntitiesPageProps) {
  const entitiesQuery = useQuery({
    queryKey: controlPlaneQueryKeys.entities(),
    queryFn: listControlPlaneEntities,
  })
  const entityQuery = useQuery({
    queryKey: controlPlaneQueryKeys.entity(entityId),
    queryFn: async () => (entityId ? getControlPlaneEntity(entityId) : null),
    enabled: Boolean(entityId),
  })
  const intentsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.intents({ entity_id: entityId ?? undefined, limit: 10 }),
    queryFn: () => listIntents({ entity_id: entityId ?? undefined, limit: 10 }),
    enabled: Boolean(entityId),
  })
  const jobsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({ entity_id: entityId ?? undefined, limit: 10 }),
    queryFn: () => listJobs({ entity_id: entityId ?? undefined, limit: 10 }),
    enabled: Boolean(entityId),
  })

  return (
    <PageScaffold
      title="Entities"
      description="Navigate authorised entities, review backend entity metadata, and inspect recent governed activity per entity."
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Available entities</h2>
              <p className="text-sm text-muted-foreground">
                {(entitiesQuery.data ?? []).length} backend-authorised entities
              </p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => void entitiesQuery.refetch()}>
              Refresh
            </Button>
          </div>
          <div className="mt-4 space-y-2">
            {(entitiesQuery.data ?? []).map((entity) => (
              <Link
                key={entity.id}
                href={`/control-plane/entities/${entity.id}`}
                className="block rounded-xl border border-border bg-background px-3 py-3"
              >
                <p className="text-sm font-semibold text-foreground">{entity.entity_name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {entity.entity_code} - {entity.gstin ?? "No GSTIN"}
                </p>
              </Link>
            ))}
          </div>
        </section>
        <section className="rounded-2xl border border-border bg-card p-4">
          {!entityId ? (
            <p className="text-sm text-muted-foreground">
              Select an entity to review its metadata and activity.
            </p>
          ) : entityQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading entity...</p>
          ) : !entityQuery.data ? (
            <p className="text-sm text-muted-foreground">
              No entity data was returned for this identifier.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 rounded-2xl border border-border bg-background p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Entity</p>
                  <p className="mt-1 text-foreground">{entityQuery.data.entity_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Code</p>
                  <p className="mt-1 text-foreground">{entityQuery.data.entity_code}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">GSTIN</p>
                  <p className="mt-1 text-foreground">{entityQuery.data.gstin ?? "Unavailable"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">GAAP</p>
                  <p className="mt-1 text-foreground">
                    {entityQuery.data.applicable_gaap ?? "Unavailable"}
                  </p>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <section className="rounded-2xl border border-border bg-background p-4">
                  <h3 className="text-sm font-semibold text-foreground">Recent intents</h3>
                  {(intentsQuery.data ?? []).length ? (
                    <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                      {(intentsQuery.data ?? []).map((intent) => (
                        <li key={intent.intent_id}>
                          <Link
                            href={`/control-plane/intents/${intent.intent_id}`}
                            className="underline underline-offset-4"
                          >
                            {intent.intent_type}
                          </Link>{" "}
                          - {intent.status}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      No recent intents for this entity.
                    </p>
                  )}
                </section>
                <section className="rounded-2xl border border-border bg-background p-4">
                  <h3 className="text-sm font-semibold text-foreground">Recent jobs</h3>
                  {(jobsQuery.data ?? []).length ? (
                    <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                      {(jobsQuery.data ?? []).map((job) => (
                        <li key={job.job_id}>
                          <Link
                            href={`/control-plane/jobs/${job.job_id}`}
                            className="underline underline-offset-4"
                          >
                            {job.job_type}
                          </Link>{" "}
                          - {job.status}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      No recent jobs for this entity.
                    </p>
                  )}
                </section>
              </div>
            </div>
          )}
        </section>
      </div>
    </PageScaffold>
  )
}
