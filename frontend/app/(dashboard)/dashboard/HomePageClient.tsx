"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Clock, Database, FileText } from "lucide-react"
import { listErpConnectors, type ErpConnector } from "@/lib/api/erp"
import { fetchAnomalyAlerts } from "@/lib/api/anomaly"
import { listJournals, type JournalRecord } from "@/lib/api/accounting-journals"
import { Skeleton } from "@/components/ui/skeleton"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toRelativeTime(dateString: string): string {
  const ms = Date.now() - new Date(dateString).getTime()
  if (Number.isNaN(ms)) return "Unknown"
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return "Yesterday"
  return `${days}d ago`
}

type SyncLabel = "Synced" | "Syncing" | "Failed" | "Never"

function connectorSyncStatus(connector: ErpConnector): {
  label: SyncLabel
  className: string
} {
  if (connector.status === "ERROR") {
    return { label: "Failed", className: "bg-destructive/10 text-destructive" }
  }
  if (connector.status === "ACTIVE" && !connector.last_sync_at) {
    return { label: "Syncing", className: "bg-blue-500/10 text-blue-400" }
  }
  if (connector.last_sync_at) {
    return { label: "Synced", className: "bg-green-500/10 text-green-400" }
  }
  return { label: "Never", className: "bg-muted text-muted-foreground" }
}

// ---------------------------------------------------------------------------
// Section 1 — Metric card
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string
  value: React.ReactNode
  subtext?: string
  href: string
  isLoading: boolean
}

function MetricCard({ label, value, subtext, href, isLoading }: MetricCardProps) {
  return (
    <Link
      href={href}
      className="group block rounded-lg bg-muted/40 p-4 transition-colors hover:bg-muted/70"
    >
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-2 min-h-[2rem]">
        {isLoading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <p className="text-2xl font-semibold text-foreground leading-none">{value}</p>
        )}
      </div>
      {subtext ? (
        <p className="mt-1 text-xs text-muted-foreground">{subtext}</p>
      ) : null}
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Section 2 — ERP data sources table
// ---------------------------------------------------------------------------

function DataSourcesCard({
  connectors,
  isLoading,
  isError,
}: {
  connectors: ErpConnector[] | undefined
  isLoading: boolean
  isError: boolean
}) {
  const rows = connectors?.slice(0, 5) ?? []

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold text-foreground">Data sources</h2>
        </div>
        <Link
          href="/erp/connectors"
          className="text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          View all →
        </Link>
      </div>

      <div className="divide-y divide-border">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <div key={`ds-skel-${i}`} className="flex items-center justify-between px-4 py-3">
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-5 w-14 rounded-full" />
            </div>
          ))
        ) : isError ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            Could not load data sources
          </div>
        ) : rows.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            No data sources connected
          </div>
        ) : (
          rows.map((connector) => {
            const badge = connectorSyncStatus(connector)
            return (
              <div
                key={connector.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground capitalize">
                    {connector.erp_type.toLowerCase().replace(/_/g, " ")}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {connector.last_sync_at
                      ? toRelativeTime(connector.last_sync_at)
                      : "Never synced"}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-[11px] font-medium",
                    badge.className,
                  )}
                >
                  {badge.label}
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 3 — Recent activity feed
// ---------------------------------------------------------------------------

function ActivityFeed({
  journals,
  isLoading,
  isError,
}: {
  journals: JournalRecord[] | undefined
  isLoading: boolean
  isError: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold text-foreground">Recent activity</h2>
      </div>

      <div className="divide-y divide-border">
        {isLoading ? (
          Array.from({ length: 8 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <div key={`act-skel-${i}`} className="flex items-start gap-3 px-4 py-3">
              <Skeleton className="mt-0.5 h-4 w-4 shrink-0 rounded" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-16" />
              </div>
            </div>
          ))
        ) : isError ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            Could not load recent activity
          </div>
        ) : !journals?.length ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            No recent activity
          </div>
        ) : (
          journals.map((journal) => (
            <Link
              key={journal.id}
              href={`/accounting/journals/${journal.id}`}
              className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">
                  {journal.narration ?? journal.journal_number}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {toRelativeTime(journal.posted_at ?? journal.journal_date)}
                </p>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 4 — Quick actions
// ---------------------------------------------------------------------------

const QUICK_ACTIONS = [
  { label: "Run GL reconciliation →", href: "/reconciliation/gl-tb" },
  { label: "Generate MIS report →", href: "/mis" },
  { label: "View anomalies →", href: "/anomalies/thresholds" },
  { label: "Sync ERP data →", href: "/erp/connectors" },
] as const

function QuickActions() {
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-foreground">Quick actions</h2>
      <div className="flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className="rounded-full border border-border bg-background px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary/50 hover:bg-muted/40 hover:text-foreground"
          >
            {action.label}
          </Link>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export default function HomePageClient() {
  const entityId = useTenantStore((state) => state.active_entity_id)

  // Sections 1 + 2: ERP connectors (shared query — one fetch for both)
  const connectorsQuery = useQuery({
    queryKey: ["home-erp-connectors"],
    queryFn: listErpConnectors,
    staleTime: 60_000,
  })

  // Section 1: Pending approvals — journals submitted for review
  const approvalsQuery = useQuery({
    queryKey: ["home-pending-approvals", entityId],
    queryFn: () =>
      listJournals({
        org_entity_id: entityId ?? undefined,
        status: "SUBMITTED",
        limit: 200,
      }),
    enabled: Boolean(entityId),
    staleTime: 30_000,
  })

  // Section 1: Open anomalies count
  const anomaliesQuery = useQuery({
    queryKey: ["home-open-anomalies"],
    queryFn: () => fetchAnomalyAlerts({ status: "OPEN", limit: 200 }),
    staleTime: 60_000,
  })

  // Section 3: Recent journal activity (10 most recent, any status)
  const journalsQuery = useQuery({
    queryKey: ["home-recent-journals", entityId],
    queryFn: () =>
      listJournals({
        org_entity_id: entityId ?? undefined,
        limit: 10,
      }),
    enabled: Boolean(entityId),
    staleTime: 30_000,
  })

  // Derive "last sync" — most recent connector sync timestamp
  const lastSyncAt =
    connectorsQuery.data
      ?.flatMap((c) => (c.last_sync_at ? [c.last_sync_at] : []))
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null

  // Safe value derivations — null → "--" when error or no entity
  const pendingCount: number | null =
    approvalsQuery.isError || !entityId ? null : (approvalsQuery.data?.length ?? null)

  const openAnomalyCount: number | null = anomaliesQuery.isError
    ? null
    : (anomaliesQuery.data?.length ?? null)

  const lastSyncValue =
    connectorsQuery.isError || !lastSyncAt ? "--" : toRelativeTime(lastSyncAt)

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Today&apos;s focus</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          An overview of your workspace right now.
        </p>
      </div>

      {/* Section 1 — Status bar */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div aria-busy={approvalsQuery.isLoading} aria-live="polite">
          <MetricCard
            label="Pending approvals"
            value={pendingCount ?? "--"}
            subtext={pendingCount === null && !approvalsQuery.isLoading ? "Not available" : undefined}
            href="/accounting/journals"
            isLoading={approvalsQuery.isLoading && Boolean(entityId)}
          />
        </div>
        <div aria-busy={connectorsQuery.isLoading} aria-live="polite">
          <MetricCard
            label="Last sync"
            value={lastSyncValue}
            subtext={connectorsQuery.isError ? "Not available" : undefined}
            href="/erp/connectors"
            isLoading={connectorsQuery.isLoading}
          />
        </div>
        <div aria-busy={anomaliesQuery.isLoading} aria-live="polite">
          <MetricCard
            label="Open anomalies"
            value={openAnomalyCount ?? "--"}
            subtext={anomaliesQuery.isError ? "Not available" : undefined}
            href="/anomalies/thresholds"
            isLoading={anomaliesQuery.isLoading}
          />
        </div>
      </div>

      {/* Sections 2 + 3 + 4 — two-column layout on lg+ */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
        {/* Left column (60%): data sources + quick actions */}
        <div className="space-y-6">
          <DataSourcesCard
            connectors={connectorsQuery.data}
            isLoading={connectorsQuery.isLoading}
            isError={connectorsQuery.isError}
          />
          <QuickActions />
        </div>

        {/* Right column (40%): recent activity */}
        <ActivityFeed
          journals={journalsQuery.data}
          isLoading={journalsQuery.isLoading && Boolean(entityId)}
          isError={journalsQuery.isError}
        />
      </div>
    </div>
  )
}
