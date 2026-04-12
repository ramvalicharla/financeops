"use client"

import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import { getDeterminism, type GovernanceSnapshotInput } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Button } from "@/components/ui/button"
import { GuardFailureCard, StateBadge } from "@/components/ui"
import { Sheet } from "@/components/ui/Sheet"

const summarizeValue = (value: unknown): string => {
  if (value === null) {
    return "null"
  }
  if (value === undefined) {
    return "-"
  }
  if (Array.isArray(value)) {
    return value.length ? `Array with ${value.length} item${value.length === 1 ? "" : "s"}` : "Empty list"
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
    return entries.length ? `${entries.length} structured field${entries.length === 1 ? "" : "s"}` : "Empty object"
  }
  return String(value)
}

function ProofCard({
  label,
  value,
  detail,
}: {
  label: string
  value: ReactNode
  detail?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 break-words text-sm text-foreground">{value}</div>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

function StructuredObjectCard({
  title,
  eyebrow,
  value,
  emptyMessage,
}: {
  title: string
  eyebrow: string
  value: Record<string, unknown> | null | undefined
  emptyMessage: string
}) {
  const entries = value ? Object.entries(value).slice(0, 6) : []

  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{eyebrow}</p>
      <h3 className="mt-1 text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {entries.length ? (
          entries.map(([key, nested]) => (
            <div key={key} className="rounded-xl border border-border bg-card px-3 py-3">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
              <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(nested)}</p>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground md:col-span-2">
            {emptyMessage}
          </div>
        )}
      </div>
    </section>
  )
}

function InputCard({
  input,
}: {
  input: GovernanceSnapshotInput
}) {
  const payloadEntries = input.input_payload ? Object.entries(input.input_payload).slice(0, 6) : []

  return (
    <article className="rounded-xl border border-border bg-card p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-foreground">{input.input_type}</p>
        <span className="font-mono text-xs text-muted-foreground">{input.snapshot_input_id}</span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <ProofCard label="Input ref" value={input.input_ref} />
        <ProofCard label="Input hash" value={input.input_hash ?? "-"} />
      </div>
      <div className="mt-3 rounded-xl border border-dashed border-border bg-background p-3">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Input payload</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {payloadEntries.length ? (
            payloadEntries.map(([key, value]) => (
              <div key={key} className="rounded-lg border border-border bg-card px-2.5 py-2">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
                <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(value)}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No structured payload was returned for this input.</p>
          )}
        </div>
      </div>
    </article>
  )
}

export function DeterminismPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedSubjectType = useControlPlaneStore((state) => state.selected_subject_type)
  const selectedSubjectId = useControlPlaneStore((state) => state.selected_subject_id)

  const query = useQuery({
    queryKey: controlPlaneQueryKeys.determinism(selectedSubjectType, selectedSubjectId),
    queryFn: async () => getDeterminism(selectedSubjectType ?? "", selectedSubjectId ?? ""),
    enabled: activePanel === "determinism" && Boolean(selectedSubjectType) && Boolean(selectedSubjectId),
  })

  const replayEntries = query.data?.replay ? Object.entries(query.data.replay).slice(0, 6) : []
  const inputEntries = query.data?.inputs ?? []

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
          <div className="flex flex-wrap gap-2">
            <StateBadge
              tone="info"
              status="determinism"
              label={`Hash ${query.data.determinism_hash.slice(0, 12)}...`}
              showIcon={false}
            />
            <StateBadge
              tone={query.data.replay_supported ? "success" : "warning"}
              status={query.data.replay_supported ? "supported" : "limited"}
              label={query.data.replay_supported ? "Replay supported" : "Replay limited"}
              showIcon={false}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <ProofCard
              label="Hash"
              value={<span className="break-all font-mono text-foreground">{query.data.determinism_hash}</span>}
            />
            <ProofCard label="Snapshot Version" value={query.data.version_no} />
            <ProofCard
              label="Replay Supported"
              value={query.data.replay_supported ? "Yes" : "No"}
              detail={
                query.data.replay_supported
                  ? "Backend replay evidence is available."
                  : "Backend replay support is not guaranteed."
              }
            />
            <ProofCard label="Trigger" value={query.data.trigger_event ?? "-"} />
          </div>

          {!query.data.replay_supported ? (
            <GuardFailureCard
              title="Replay not guaranteed"
              message="The backend does not currently guarantee replay support for this subject."
              recommendation="Use snapshot hashes and the input list below as the authoritative evidence trail."
              tone="warning"
            />
          ) : null}

          <StructuredObjectCard
            title="Replay evidence"
            eyebrow="Replay result"
            value={query.data.replay ?? null}
            emptyMessage="The backend returned no structured replay body for this subject."
          />

          <section className="space-y-3 rounded-2xl border border-border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Inputs</p>
                <p className="text-sm text-foreground">
                  Backend-provided inputs used to derive the determinism proof.
                </p>
              </div>
              <StateBadge
                tone={inputEntries.length ? "success" : "neutral"}
                status={inputEntries.length ? "available" : "empty"}
                label={inputEntries.length ? `${inputEntries.length} input(s)` : "No inputs"}
                showIcon={false}
              />
            </div>

            {inputEntries.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {inputEntries.map((input) => (
                  <InputCard key={input.snapshot_input_id} input={input} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">The backend returned no determinism inputs for this subject.</p>
            )}
          </section>

          <Button type="button" variant="outline" onClick={() => void query.refetch()}>
            Refresh Determinism
          </Button>
        </div>
      )}
    </Sheet>
  )
}
