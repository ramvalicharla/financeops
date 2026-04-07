"use client"

import { useEffect, useState } from "react"
import { DataTable } from "@/components/admin/DataTable"
import { ToggleSwitch } from "@/components/admin/ToggleSwitch"
import {
  listPlatformTenants,
  updatePlatformTenantStatus,
} from "@/lib/api/platform-admin"
import type { PlatformTenant } from "@/lib/types/platform-admin"

export default function AdminTenantsPage() {
  const [rows, setRows] = useState<PlatformTenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listPlatformTenants({ limit: 200, offset: 0 })
      setRows(payload.data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load tenants")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const onToggle = async (tenant: PlatformTenant, enabled: boolean) => {
    setMessage(null)
    setError(null)
    try {
      await updatePlatformTenantStatus(tenant.id, enabled ? "active" : "suspended")
      setMessage(`Tenant ${tenant.slug} ${enabled ? "activated" : "suspended"}.`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update tenant status")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Tenants</h1>
        <p className="text-sm text-muted-foreground">
          View tenant status and activate or suspend access.
        </p>
      </header>

      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading tenants...</p> : null}

      <DataTable
        rows={rows}
        emptyMessage="No tenants found."
        columns={[
          {
            key: "display_name",
            header: "Tenant",
            render: (row) => (
              <div>
                <p className="font-medium text-foreground">{row.display_name}</p>
                <p className="text-xs text-muted-foreground">{row.slug}</p>
              </div>
            ),
          },
          {
            key: "tenant_id",
            header: "Tenant ID",
            render: (row) => <code className="text-xs text-muted-foreground">{row.id}</code>,
          },
          {
            key: "status",
            header: "Status",
            render: (row) => <span className="text-foreground">{row.status}</span>,
          },
          {
            key: "type",
            header: "Type",
            render: (row) => <span className="text-muted-foreground">{row.tenant_type}</span>,
          },
          {
            key: "org_setup",
            header: "Org Setup",
            render: (row) => (
              <span className="text-muted-foreground">
                {row.org_setup_complete ? "Complete" : `Step ${row.org_setup_step}`}
              </span>
            ),
          },
          {
            key: "active",
            header: "Active",
            render: (row) => (
              <ToggleSwitch
                checked={row.status === "active"}
                onChange={(next) => {
                  void onToggle(row, next)
                }}
                onLabel="Active"
                offLabel="Suspended"
              />
            ),
          },
        ]}
      />
    </div>
  )
}
