"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Plus } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { listUserOrgs, type OrgSummary, type SubscriptionTier } from "@/lib/api/orgs"
import { cn } from "@/lib/utils"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIER_LABEL: Record<SubscriptionTier, string> = {
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
}

const TIER_CLASS: Record<SubscriptionTier, string> = {
  starter: "bg-muted text-muted-foreground",
  pro: "bg-[hsl(var(--brand-primary)/0.15)] text-[hsl(var(--brand-primary))]",
  enterprise: "bg-purple-500/15 text-purple-400",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return "Never active"
  const then = new Date(timestamp).getTime()
  if (Number.isNaN(then)) return "Unknown"
  const diffMs = Date.now() - then
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return "Active today"
  if (diffDays === 1) return "Active yesterday"
  if (diffDays < 30) return `Active ${diffDays} days ago`
  const diffMonths = Math.floor(diffDays / 30)
  if (diffMonths === 1) return "Active 1 month ago"
  return `Active ${diffMonths} months ago`
}

function formatEntityCount(count: number): string {
  return count === 1 ? "1 entity" : `${count} entities`
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TierBadge({ tier }: { tier: SubscriptionTier }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        TIER_CLASS[tier],
      )}
    >
      {TIER_LABEL[tier]}
    </span>
  )
}

function OrgCard({ org }: { org: OrgSummary }) {
  return (
    <Link
      href={`/dashboard?org=${org.tenant_slug}`}
      className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-lg"
      aria-label={`Enter ${org.display_name}`}
    >
      <Card className="h-full transition-colors hover:border-primary/60 hover:bg-card/80">
        <CardContent className="p-5">
          <div className="mb-3 flex items-start justify-between gap-3">
            <p className="text-sm font-semibold text-foreground transition-colors group-hover:text-primary">
              {org.display_name}
            </p>
            <TierBadge tier={org.subscription_tier} />
          </div>
          <p className="text-xs text-muted-foreground">
            {formatEntityCount(org.entity_count)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatRelativeTime(org.last_active_at)}
          </p>
        </CardContent>
      </Card>
    </Link>
  )
}

function NewOrgCard() {
  return (
    <Link
      href="/org-setup"
      className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-lg"
      aria-label="Create a new organisation"
    >
      <Card className="h-full border-dashed transition-colors hover:border-primary/60">
        <CardContent className="flex h-full min-h-[108px] items-center justify-center p-5">
          <div className="flex items-center gap-2 text-muted-foreground transition-colors group-hover:text-foreground">
            <Plus className="h-4 w-4" />
            <span className="text-sm">New organisation</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function OrgSkeletonGrid() {
  return (
    <div
      className="grid gap-4 md:grid-cols-2"
      aria-label="Loading organisations"
      aria-busy={true}
    >
      {Array.from({ length: 4 }).map((_, index) => (
        // key is index-based intentionally — skeleton items have no stable identity
        // eslint-disable-next-line react/no-array-index-key
        <Card key={`org-skeleton-${index}`} className="h-full">
          <CardContent className="p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-14 rounded-full" />
            </div>
            <Skeleton className="mt-2 h-3 w-20" />
            <Skeleton className="mt-2 h-3 w-28" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; orgs: OrgSummary[] }

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OrgsPageClient() {
  const router = useRouter()
  const [state, setState] = useState<LoadState>({ status: "loading" })

  const loadOrgs = useCallback(async () => {
    setState({ status: "loading" })
    try {
      const orgs = await listUserOrgs()
      // Single (or zero) org — skip the picker and go straight to the dashboard.
      if (orgs.length <= 1) {
        router.replace("/dashboard")
        return
      }
      setState({ status: "ready", orgs })
    } catch (cause) {
      setState({
        status: "error",
        message:
          cause instanceof Error
            ? cause.message
            : "Could not load organisations. Try again.",
      })
    }
  }, [router])

  useEffect(() => {
    void loadOrgs()
  }, [loadOrgs])

  return (
    <div className="space-y-4">
      {/* Page heading — matches the login card header style */}
      <div className="mb-2 space-y-1">
        <h2 className="text-xl font-semibold text-foreground">
          Choose an organisation
        </h2>
        <p className="text-sm text-muted-foreground">
          Select the workspace you want to enter
        </p>
      </div>

      {state.status === "loading" && <OrgSkeletonGrid />}

      {state.status === "error" && (
        <div
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-6 text-center"
          role="alert"
        >
          <p className="mb-4 text-sm text-destructive">{state.message}</p>
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm text-foreground transition-colors hover:bg-muted"
            onClick={() => void loadOrgs()}
          >
            Try again
          </button>
        </div>
      )}

      {state.status === "ready" && (
        <div className="grid gap-4 md:grid-cols-2">
          {state.orgs.map((org) => (
            <OrgCard key={org.tenant_id} org={org} />
          ))}
          <NewOrgCard />
        </div>
      )}
    </div>
  )
}
