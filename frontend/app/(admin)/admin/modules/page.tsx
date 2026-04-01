"use client"

import { useEffect, useState } from "react"
import { DataTable } from "@/components/admin/DataTable"
import { ToggleSwitch } from "@/components/admin/ToggleSwitch"
import { listPlatformModules, togglePlatformModule } from "@/lib/api/platform-admin"
import type { ServiceRegistryModule } from "@/lib/types/service-registry"

export default function AdminModulesPage() {
  const [rows, setRows] = useState<ServiceRegistryModule[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const payload = await listPlatformModules()
      setRows(payload)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load modules")
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const onToggle = async (row: ServiceRegistryModule, next: boolean) => {
    setError(null)
    setMessage(null)
    try {
      await togglePlatformModule(row.module_name, next)
      setMessage(`Module ${row.module_name} ${next ? "enabled" : "disabled"}.`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to toggle module")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Modules</h1>
        <p className="text-sm text-muted-foreground">
          Enable or disable modules at the control-plane level.
        </p>
      </header>

      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <DataTable
        rows={rows}
        emptyMessage="No modules found."
        columns={[
          {
            key: "module_name",
            header: "Module",
            render: (row) => (
              <div>
                <p className="font-medium text-foreground">{row.module_name}</p>
                <p className="text-xs text-muted-foreground">{row.module_version}</p>
              </div>
            ),
          },
          {
            key: "health",
            header: "Health",
            render: (row) => row.health_status,
          },
          {
            key: "route_prefix",
            header: "Route",
            render: (row) => row.route_prefix ?? "-",
          },
          {
            key: "enabled",
            header: "Enabled",
            render: (row) => (
              <ToggleSwitch
                checked={row.is_enabled}
                onChange={(next) => {
                  void onToggle(row, next)
                }}
                onLabel="Enabled"
                offLabel="Disabled"
              />
            ),
          },
        ]}
      />
    </div>
  )
}
