"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listIntents } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { IntentBody } from "@/components/control-plane/bodies/IntentBody"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { Button } from "@/components/ui/button"

interface ControlPlaneIntentsPageProps {
  intentId?: string | null
}

export function ControlPlaneIntentsPage({ intentId }: ControlPlaneIntentsPageProps) {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const [selectedIntentId, setSelectedIntentId] = useState<string | null>(intentId ?? null)
  const intentsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.intents({ entity_id: activeEntityId ?? undefined, limit: 50 }),
    queryFn: () => listIntents({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })

  const rows = intentsQuery.data ?? []
  const resolvedIntentId = intentId ?? selectedIntentId ?? rows[0]?.intent_id ?? null
  const openCount = useMemo(
    () => rows.filter((row) => !["RECORDED", "REJECTED", "CANCELLED"].includes(row.status)).length,
    [rows],
  )

  return (
    <PageScaffold
      title="Intents"
      description="Review governed actions as backend-returned intents. Legal transitions and execution remain backend-authoritative."
      actions={
        <Button
          type="button"
          disabled
          title="Intent composition is unavailable in the current backend contract."
        >
          Create Intent
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Intent list</h2>
              <p className="text-sm text-muted-foreground">{openCount} open intents in current scope.</p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => void intentsQuery.refetch()}>
              Refresh
            </Button>
          </div>
          {intentsQuery.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading intents...</p>
          ) : !rows.length ? (
            <p className="mt-4 text-sm text-muted-foreground">No intents were returned for this scope.</p>
          ) : (
            <div className="mt-4 space-y-2">
              {rows.map((intent) => {
                const isActive = resolvedIntentId === intent.intent_id
                return (
                  <article
                    key={intent.intent_id}
                    className={`rounded-xl border p-3 ${isActive ? "border-foreground bg-background" : "border-border bg-background/60"}`}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => setSelectedIntentId(intent.intent_id)}
                    >
                      <p className="text-sm font-semibold text-foreground">{intent.intent_type}</p>
                      <p className="mt-1 font-mono text-xs text-muted-foreground">{intent.intent_id}</p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {intent.status} - {intent.module_key} - {intent.requested_at ?? "No timestamp"}
                      </p>
                    </button>
                    <Link
                      href={`/control-plane/intents/${intent.intent_id}`}
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
          <IntentBody intentId={resolvedIntentId} showRefreshButton={false} />
        </section>
      </div>
    </PageScaffold>
  )
}
