"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import apiClient from "@/lib/api/client"
import { getMarketplaceStats } from "@/lib/api/marketplace"
import { getServiceDashboard } from "@/lib/api/service-registry"
import { listWhiteLabelAdminConfigs } from "@/lib/api/white-label"

type OpsStats = {
  totalTenants: number
  revenueThisMonth: number
  aiCostTodayUsd: string
  failedJobs: number
  securityEvents24h: number
}

export default function AdminHomePage() {
  const [stats, setStats] = useState<OpsStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [tenants, marketplace, serviceDashboard, benchmark] = await Promise.all([
          listWhiteLabelAdminConfigs({ limit: 1, offset: 0 }),
          getMarketplaceStats(),
          getServiceDashboard(),
          apiClient.get<{
            data: Array<{ total_cost_usd: string }>
            total: number
            limit: number
            offset: number
          }>("/api/v1/learning/benchmark/results?limit=1&offset=0"),
        ])

        const failedJobs = serviceDashboard.tasks.filter(
          (task) => task.last_run_status === "failure" || task.last_run_status === "timeout",
        ).length

        setStats({
          totalTenants: tenants.total,
          revenueThisMonth: marketplace.total_revenue_credits,
          aiCostTodayUsd: benchmark.data.data[0]?.total_cost_usd ?? "0.000000",
          failedJobs,
          securityEvents24h: serviceDashboard.unhealthy_modules.length,
        })
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load admin stats")
      }
    }

    void load()
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Platform Operations Console</h1>
        <p className="text-sm text-muted-foreground">Cross-platform operational view for owners and admins.</p>
      </header>

      {error ? (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-5">
        <MetricCard label="Total tenants" value={stats ? String(stats.totalTenants) : "..."} />
        <MetricCard label="Revenue this month" value={stats ? String(stats.revenueThisMonth) : "..."} />
        <MetricCard label="AI cost today (USD)" value={stats ? stats.aiCostTodayUsd : "..."} />
        <MetricCard label="Failed jobs" value={stats ? String(stats.failedJobs) : "..."} />
        <MetricCard label="Security events (24h)" value={stats ? String(stats.securityEvents24h) : "..."} />
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-lg font-medium text-foreground">Quick Links</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <QuickLink href="/admin/white-label" title="Tenant management" description="Tenant configurations and branding status." />
          <QuickLink href="/admin/service-registry" title="Service registry" description="Module health, tasks, and queue status." />
          <QuickLink href="/admin/marketplace" title="Marketplace" description="Template marketplace revenue and moderation." />
          <QuickLink href="/dashboard/partner" title="Partner program" description="Partner referrals, commissions, and applications." />
        </div>
      </section>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
    </article>
  )
}

function QuickLink({
  href,
  title,
  description,
}: {
  href: string
  title: string
  description: string
}) {
  return (
    <Link href={href} className="rounded-lg border border-border p-3 transition hover:border-blue-500/60">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="text-xs text-muted-foreground">{description}</p>
    </Link>
  )
}
