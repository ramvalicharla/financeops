"use client"

import { ArrowRight, GitBranch, Network, Waypoints } from "lucide-react"

import { StateBadge } from "@/components/ui/StateBadge"
import { cn } from "@/lib/utils"

export type LineageRecord = Record<string, unknown>

export interface LineageNodeSummary {
  id: string
  title: string
  subtitle: string | null
  badges: Array<{
    label: string
    tone: "default" | "neutral" | "success" | "warning" | "danger" | "info"
  }>
  details: Array<{
    label: string
    value: string
  }>
}

export interface LineageEdgeSummary {
  id: string
  label: string
  from: string
  to: string
}

interface LineageGraphProps {
  direction: "forward" | "reverse"
  title: string
  rootLabel: string
  rootHint: string
  nodes: LineageRecord[]
  edges: LineageRecord[]
  emptyMessage: string
  className?: string
}

const STATUS_TONE_MAP: Record<string, "default" | "neutral" | "success" | "warning" | "danger" | "info"> = {
  failed: "danger",
  error: "danger",
  rejected: "danger",
  blocked: "warning",
  warning: "warning",
  pending: "neutral",
  queued: "neutral",
  draft: "neutral",
  running: "info",
  in_progress: "info",
  active: "info",
  complete: "success",
  completed: "success",
  approved: "success",
  posted: "success",
  closed: "success",
  authoritative: "info",
  limited: "warning",
}

const getText = (record: LineageRecord, keys: string[]): string | null => {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value)
    }
  }
  return null
}

const getShortId = (value: string, length = 10): string =>
  value.length <= length ? value : `${value.slice(0, Math.max(4, length - 4))}...${value.slice(-4)}`

const formatTimestamp = (value: string | null): string | null => {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

const resolveTone = (value: string | null): LineageNodeSummary["badges"][number]["tone"] => {
  if (!value) {
    return "default"
  }
  const normalized = value.trim().toLowerCase().replace(/\s+/g, "_")
  for (const [needle, tone] of Object.entries(STATUS_TONE_MAP)) {
    if (normalized.includes(needle)) {
      return tone
    }
  }
  return "neutral"
}

const describeNode = (record: LineageRecord, index: number): LineageNodeSummary => {
  const runId = getText(record, ["run_id"])
  const snapshotId = getText(record, ["snapshot_id"])
  const subjectType = getText(record, ["subject_type"])
  const subjectId = getText(record, ["subject_id"])
  const moduleCode = getText(record, ["module_code", "module_key"])
  const status = getText(record, ["status"])
  const snapshotKind = getText(record, ["snapshot_kind"])
  const versionNo = getText(record, ["version_no"])
  const determinismHash = getText(record, ["determinism_hash"])
  const runToken = getText(record, ["run_token"])
  const triggerEvent = getText(record, ["trigger_event"])
  const replaySupported = record.replay_supported
  const title =
    subjectType && subjectId
      ? `${subjectType}:${getShortId(subjectId, 14)}`
      : runId
        ? `run:${getShortId(runId, 14)}`
        : snapshotId
          ? `snapshot:${getShortId(snapshotId, 14)}`
          : moduleCode
            ? moduleCode
            : `node-${index + 1}`
  const subtitle =
    moduleCode ??
    (status ? `Status ${status}` : null) ??
    (snapshotKind ? `Snapshot kind ${snapshotKind}` : null) ??
    null
  const details = [
    subjectType && subjectId ? { label: "Subject", value: `${subjectType}:${subjectId}` } : null,
    runId ? { label: "Run", value: runId } : null,
    snapshotId ? { label: "Snapshot", value: snapshotId } : null,
    moduleCode ? { label: "Module", value: moduleCode } : null,
    status ? { label: "Status", value: status } : null,
    versionNo ? { label: "Version", value: versionNo } : null,
    snapshotKind ? { label: "Kind", value: snapshotKind } : null,
    triggerEvent ? { label: "Trigger", value: triggerEvent } : null,
    determinismHash ? { label: "Hash", value: getShortId(determinismHash, 18) } : null,
    runToken ? { label: "Token", value: getShortId(runToken, 18) } : null,
    typeof replaySupported === "boolean"
      ? { label: "Replay", value: replaySupported ? "Supported" : "Limited" }
      : null,
    formatTimestamp(getText(record, ["snapshot_at", "occurred_at"])) ? {
      label: "Observed",
      value: formatTimestamp(getText(record, ["snapshot_at", "occurred_at"])) ?? "",
    } : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>

  const badges = [
    { label: runId ? "Run" : snapshotId ? "Snapshot" : subjectType ?? "Node", tone: "info" as const },
    status ? { label: status, tone: resolveTone(status) } : null,
    snapshotKind ? { label: snapshotKind, tone: "neutral" as const } : null,
  ].filter(Boolean) as LineageNodeSummary["badges"]

  return {
    id: runId ?? snapshotId ?? subjectId ?? title,
    title,
    subtitle,
    badges,
    details,
  }
}

const describeEdge = (record: LineageRecord, index: number): LineageEdgeSummary => {
  const from =
    getText(record, ["from_run_id", "from_subject_id", "from_snapshot_id"]) ??
    "unknown"
  const to =
    getText(record, ["to_run_id", "to_subject_id", "to_snapshot_id"]) ??
    "unknown"
  const label = getText(record, ["kind", "relationship", "edge_type"]) ?? "relationship"
  return {
    id: `${from}-${label}-${to}-${index}`,
    from,
    to,
    label,
  }
}

export function summarizeLineageNode(record: LineageRecord, index = 0): LineageNodeSummary {
  return describeNode(record, index)
}

export function summarizeLineageEdge(record: LineageRecord, index = 0): LineageEdgeSummary {
  return describeEdge(record, index)
}

export function LineageGraph({
  direction,
  title,
  rootLabel,
  rootHint,
  nodes,
  edges,
  emptyMessage,
  className,
}: LineageGraphProps) {
  const nodeSummaries = nodes.map((node, index) => describeNode(node, index))
  const edgeSummaries = edges.map((edge, index) => describeEdge(edge, index))
  const hasStructure = nodeSummaries.length > 0 || edgeSummaries.length > 0
  const directionLabel = direction === "forward" ? "Forward" : "Reverse"

  return (
    <section className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{title}</h3>
            <StateBadge label={directionLabel} tone="info" />
          </div>
          <p className="text-sm text-muted-foreground">{rootHint}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StateBadge label={`${nodeSummaries.length} nodes`} tone={nodeSummaries.length ? "success" : "neutral"} />
          <StateBadge label={`${edgeSummaries.length} edges`} tone={edgeSummaries.length ? "success" : "neutral"} />
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-background p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge label="Root" tone="default" />
          <span className="break-all font-mono text-sm text-foreground">{rootLabel}</span>
        </div>
      </div>

      {!hasStructure ? (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-muted/20 p-4 text-sm text-muted-foreground">
          {emptyMessage}
        </div>
      ) : (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(16rem,0.7fr)]">
          <ol className="space-y-3">
            {nodeSummaries.map((node, index) => {
              const isLast = index === nodeSummaries.length - 1
              return (
                <li key={node.id} className="relative pl-8">
                  <span
                    aria-hidden="true"
                    className="absolute left-2 top-5 h-3 w-3 rounded-full border border-border bg-background shadow-sm"
                  />
                  {!isLast ? (
                    <span
                      aria-hidden="true"
                      className="absolute bottom-0 left-[0.625rem] top-8 w-px bg-border"
                    />
                  ) : null}
                  <article className="rounded-xl border border-border bg-card/80 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-foreground">{node.title}</p>
                        {node.subtitle ? <p className="text-sm text-muted-foreground">{node.subtitle}</p> : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {node.badges.map((badge) => (
                          <StateBadge key={`${node.id}-${badge.label}`} label={badge.label} tone={badge.tone} />
                        ))}
                      </div>
                    </div>
                    {node.details.length ? (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {node.details.map((detail) => (
                          <div key={`${node.id}-${detail.label}`} className="rounded-lg border border-border bg-background px-3 py-2">
                            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                              {detail.label}
                            </p>
                            <p className="mt-1 break-all text-sm text-foreground">{detail.value}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                </li>
              )
            })}
          </ol>

          <aside className="rounded-2xl border border-border bg-muted/10 p-4">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm font-semibold text-foreground">Edge operator view</p>
            </div>
            <div className="mt-3 space-y-2">
              {edgeSummaries.length ? (
                edgeSummaries.map((edge) => (
                  <div key={edge.id} className="rounded-xl border border-border bg-card px-3 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <StateBadge label={edge.label} tone="neutral" />
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">Connection</span>
                    </div>
                    <div className="mt-2 flex items-start gap-2 text-xs text-muted-foreground">
                      <span className="break-all font-mono text-foreground">{getShortId(edge.from, 16)}</span>
                      <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span className="break-all font-mono text-foreground">{getShortId(edge.to, 16)}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                  {direction === "forward"
                    ? "The backend returned nodes without explicit dependency edges."
                    : "The backend returned reverse nodes without explicit dependency edges."}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}

      {!hasStructure ? null : (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Graph lanes are rendered from backend-returned nodes and edges only.</span>
          <Waypoints className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Shallow payloads degrade into a structured node list.</span>
        </div>
      )}
    </section>
  )
}
