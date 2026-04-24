"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Search, Filter, AlertTriangle } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { adminListTenants } from "@/lib/api/admin"
import type { AdminTenantListItem } from "@/lib/types/admin"

const STATUS_OPTIONS = ["all", "active", "trialing", "suspended", "pending"] as const
const PLAN_OPTIONS = ["all", "starter", "growth", "pro", "enterprise"] as const

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function formatTrialDays(iso: string | null): string {
  if (!iso) return "—"
  const now = Date.now()
  const end = new Date(iso).getTime()
  const diff = Math.ceil((end - now) / (24 * 60 * 60 * 1000))
  if (diff < 0) return "Expired"
  if (diff === 0) return "Today"
  return `${diff}d`
}

function TableSkeleton() {
  return (
    <>
      {[...Array(8)].map((_, i) => (
        <TableRow key={i}>
          <TableCell><Skeleton className="h-4 w-36" /></TableCell>
          <TableCell><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell><Skeleton className="h-4 w-10" /></TableCell>
          <TableCell><Skeleton className="h-4 w-12" /></TableCell>
          <TableCell><Skeleton className="h-4 w-8" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
        </TableRow>
      ))}
    </>
  )
}

export function AdminTenantsPageClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [items, setItems] = useState<AdminTenantListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get("filter") ?? "all")
  const [planFilter, setPlanFilter] = useState<string>("all")

  useEffect(() => {
    adminListTenants({ limit: 200 })
      .then((res) => setItems(res.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load tenants"))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let list = items
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.slug.toLowerCase().includes(q),
      )
    }
    if (statusFilter !== "all") {
      list = list.filter((t) => t.status?.toLowerCase() === statusFilter)
    }
    if (planFilter !== "all") {
      list = list.filter((t) => t.plan_tier?.toLowerCase() === planFilter)
    }
    return list
  }, [items, query, statusFilter, planFilter])

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Tenants</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {loading ? "Loading..." : `${filtered.length} of ${items.length} tenants`}
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or slug…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {s === "all" ? "All Status" : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex gap-1 flex-wrap">
            {PLAN_OPTIONS.map((p) => (
              <button
                key={p}
                onClick={() => setPlanFilter(p)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  planFilter === p
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {p === "all" ? "All Plans" : p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Name</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Trial Expiry</TableHead>
                <TableHead className="text-right">Credits</TableHead>
                <TableHead className="text-right">Users</TableHead>
                <TableHead>Joined</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableSkeleton />
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-12 text-center text-sm text-muted-foreground">
                    No tenants match your filters.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((t) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/control-plane/admin/tenants/${t.id}`)}
                  >
                    <TableCell className="pl-4">
                      <div>
                        <p className="font-medium text-sm">{t.name}</p>
                        <p className="text-xs text-muted-foreground">{t.slug}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground capitalize">
                        {t.plan_tier ?? "—"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={t.status ?? "unknown"} />
                    </TableCell>
                    <TableCell>
                      <span
                        className={`text-xs font-medium ${
                          t.trial_end_date &&
                          new Date(t.trial_end_date).getTime() - Date.now() < 3 * 24 * 60 * 60 * 1000 &&
                          new Date(t.trial_end_date).getTime() > Date.now()
                            ? "text-amber-400"
                            : "text-muted-foreground"
                        }`}
                      >
                        {formatTrialDays(t.trial_end_date)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {t.credit_balance.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {t.user_count}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(t.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
