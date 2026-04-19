"use client"

import { useCallback, useEffect, useState } from "react"
import { approvePartner, getPartnerAdminStats, listPartnerApplications } from "@/lib/api/partner"
import type { PartnerProfile } from "@/lib/types/partner"
import { toast } from "sonner"

interface PartnerAdminStats {
  total_partners: number
  pending_applications: number
  total_commissions: string
  total_conversions: number
}

export default function AdminPartnersPage() {
  const [applications, setApplications] = useState<PartnerProfile[]>([])
  const [stats, setStats] = useState<PartnerAdminStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  const load = useCallback(async () => {
    setError(null)
    try {
      const [appsPayload, statsPayload] = await Promise.all([
        listPartnerApplications({ limit: 200, offset: 0 }),
        getPartnerAdminStats(),
      ])
      setApplications(appsPayload.data)
      setStats(statsPayload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load partner admin data")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const approve = async (partnerId: string) => {
        setError(null)
    try {
      await approvePartner(partnerId)
      toast.success("Partner approved.")
      await load()
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Failed to approve partner")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Partner Applications</h1>
        <p className="text-sm text-muted-foreground">Review pending partner applications and monitor partner performance.</p>
      </header>

      {stats ? (
        <section className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Total Partners</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_partners}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Pending</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.pending_applications}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Total Conversions</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_conversions}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Total Commissions</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{stats.total_commissions}</p>
          </div>
        </section>
      ) : null}

            {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Pending Applications</h2>
        </div>
        <div className="divide-y divide-border/60">
          {applications.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-foreground">{row.company_name}</p>
                <p className="text-xs text-muted-foreground">{row.contact_email} | {row.partner_tier}</p>
              </div>
              <button
                type="button"
                onClick={() => void approve(row.id)}
                className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
              >
                Approve
              </button>
            </div>
          ))}
          {applications.length === 0 ? (
            <p className="px-4 py-4 text-sm text-muted-foreground">No pending applications.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
