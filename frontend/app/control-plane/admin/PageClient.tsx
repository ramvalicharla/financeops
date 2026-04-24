"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Users, CreditCard, Clock, TrendingUp, AlertTriangle, ArrowRight } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { adminListTenants } from "@/lib/api/admin"
import type { AdminTenantListItem } from "@/lib/types/admin"

type DashboardStats = {
  total: number
  active: number
  trialing: number
  suspended: number
  mrr: number
}

const PLAN_PRICE: Record<string, number> = {
  starter: 49,
  growth: 149,
  pro: 399,
  enterprise: 999,
}

function computeStats(items: AdminTenantListItem[]): DashboardStats {
  let active = 0
  let trialing = 0
  let suspended = 0
  let mrr = 0

  for (const t of items) {
    const status = t.status?.toLowerCase()
    if (status === "active") active++
    else if (status === "trialing") trialing++
    else if (status === "suspended") suspended++

    if (t.plan_tier) {
      const tier = t.plan_tier.toLowerCase()
      mrr += PLAN_PRICE[tier] ?? 0
    }
  }

  return { total: items.length, active, trialing, suspended, mrr }
}

function getTrialsExpiringWithin7Days(items: AdminTenantListItem[]): AdminTenantListItem[] {
  const now = Date.now()
  const seven = 7 * 24 * 60 * 60 * 1000
  return items.filter((t) => {
    if (!t.trial_end_date) return false
    const end = new Date(t.trial_end_date).getTime()
    return end > now && end - now <= seven
  })
}

function getRecentSignups(items: AdminTenantListItem[]): AdminTenantListItem[] {
  return [...items]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 10)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n)
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  color: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
          <p className="text-2xl font-semibold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-16" />
        </div>
      </CardContent>
    </Card>
  )
}

export function AdminDashboardPageClient() {
  const [items, setItems] = useState<AdminTenantListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminListTenants({ limit: 200 })
      .then((res) => setItems(res.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load tenants"))
      .finally(() => setLoading(false))
  }, [])

  const stats = computeStats(items)
  const expiringTrials = getTrialsExpiringWithin7Days(items)
  const recentSignups = getRecentSignups(items)

  return (
    <div className="space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Platform Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Overview of all tenant accounts and subscriptions.</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard icon={Users} label="Total Tenants" value={stats.total} color="bg-blue-500/20 text-blue-400" />
            <StatCard icon={CreditCard} label="Active Subscriptions" value={stats.active} color="bg-emerald-500/20 text-emerald-400" />
            <StatCard icon={Clock} label="Trialing" value={stats.trialing} color="bg-amber-500/20 text-amber-400" />
            <StatCard icon={TrendingUp} label="Est. MRR" value={formatCurrency(stats.mrr)} color="bg-purple-500/20 text-purple-400" />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Trials expiring in 7 days */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-medium">Trials Expiring in 7 Days</CardTitle>
            {!loading && expiringTrials.length > 0 && (
              <Link
                href="/control-plane/admin/tenants?filter=trialing"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            )}
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-4 w-24 ml-auto" />
                  </div>
                ))}
              </div>
            ) : expiringTrials.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No trials expiring this week.</p>
            ) : (
              <ul className="divide-y divide-border">
                {expiringTrials.map((t) => (
                  <li key={t.id} className="flex items-center justify-between py-2.5 gap-2">
                    <Link
                      href={`/control-plane/admin/tenants/${t.id}`}
                      className="text-sm font-medium hover:underline truncate max-w-[200px]"
                    >
                      {t.name}
                    </Link>
                    <span className="text-xs text-muted-foreground shrink-0">
                      Expires {t.trial_end_date ? formatDate(t.trial_end_date) : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Recent signups */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-medium">Recent Signups</CardTitle>
            <Link
              href="/control-plane/admin/tenants"
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              All tenants <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-5 w-16 ml-auto rounded-full" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                ))}
              </div>
            ) : recentSignups.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No tenants yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {recentSignups.map((t) => (
                  <li key={t.id} className="flex items-center gap-2 py-2.5">
                    <Link
                      href={`/control-plane/admin/tenants/${t.id}`}
                      className="text-sm font-medium hover:underline truncate flex-1 min-w-0"
                    >
                      {t.name}
                    </Link>
                    <StatusBadge status={t.status} />
                    <span className="text-xs text-muted-foreground shrink-0">{formatDate(t.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
