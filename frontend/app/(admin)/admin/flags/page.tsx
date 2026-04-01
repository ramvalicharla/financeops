"use client"

import { useEffect, useMemo, useState } from "react"
import { DataTable } from "@/components/admin/DataTable"
import { TenantSelector } from "@/components/admin/TenantSelector"
import { ToggleSwitch } from "@/components/admin/ToggleSwitch"
import {
  createFeatureFlag,
  deleteFeatureFlag,
  listFeatureFlags,
  listPlatformModules,
  listPlatformTenants,
  updateFeatureFlag,
} from "@/lib/api/platform-admin"
import type { PlatformFeatureFlag, PlatformTenant } from "@/lib/types/platform-admin"
import type { ServiceRegistryModule } from "@/lib/types/service-registry"

const nowIso = () => new Date().toISOString()

export default function AdminFlagsPage() {
  const [rows, setRows] = useState<PlatformFeatureFlag[]>([])
  const [tenants, setTenants] = useState<PlatformTenant[]>([])
  const [modules, setModules] = useState<ServiceRegistryModule[]>([])
  const [selectedTenant, setSelectedTenant] = useState("")
  const [selectedModule, setSelectedModule] = useState("")
  const [flagKey, setFlagKey] = useState("")
  const [scopeType, setScopeType] = useState<"tenant" | "user" | "entity" | "canary">("tenant")
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const [tenantPayload, modulePayload] = await Promise.all([
        listPlatformTenants({ limit: 200, offset: 0 }),
        listPlatformModules(),
      ])
      setTenants(tenantPayload.data)
      setModules(modulePayload)

      const tenantId = selectedTenant || tenantPayload.data[0]?.id || ""
      if (tenantId && !selectedTenant) {
        setSelectedTenant(tenantId)
      }
      const items = await listFeatureFlags({ tenant_id: tenantId || undefined })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load feature flags")
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selectedTenant) return
    void (async () => {
      try {
        const items = await listFeatureFlags({ tenant_id: selectedTenant })
        setRows(items)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Failed to load feature flags")
      }
    })()
  }, [selectedTenant])

  const moduleMap = useMemo(
    () => new Map(modules.map((module) => [module.id, module.module_name])),
    [modules],
  )

  const onCreate = async () => {
    if (!selectedTenant || !selectedModule || !flagKey.trim()) {
      setError("Tenant, module, and flag key are required.")
      return
    }
    setError(null)
    setMessage(null)
    try {
      await createFeatureFlag(selectedTenant, {
        module_id: selectedModule,
        flag_key: flagKey.trim(),
        flag_value: {},
        rollout_mode: "on",
        compute_enabled: true,
        write_enabled: true,
        visibility_enabled: true,
        target_scope_type: scopeType,
        target_scope_id: null,
        traffic_percent: scopeType === "canary" ? 10 : null,
        effective_from: nowIso(),
        effective_to: null,
      })
      setFlagKey("")
      setMessage("Feature flag created.")
      const items = await listFeatureFlags({ tenant_id: selectedTenant })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create feature flag")
    }
  }

  const onToggle = async (row: PlatformFeatureFlag, enabled: boolean) => {
    setError(null)
    setMessage(null)
    try {
      await updateFeatureFlag(row.id, { enabled })
      setMessage(`Flag ${row.flag_key} ${enabled ? "enabled" : "disabled"}.`)
      const items = await listFeatureFlags({ tenant_id: selectedTenant || undefined })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update feature flag")
    }
  }

  const onDelete = async (row: PlatformFeatureFlag) => {
    setError(null)
    setMessage(null)
    try {
      await deleteFeatureFlag(row.id)
      setMessage(`Flag ${row.flag_key} deleted.`)
      const items = await listFeatureFlags({ tenant_id: selectedTenant || undefined })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to delete feature flag")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Feature Flags</h1>
        <p className="text-sm text-muted-foreground">
          Manage global and scoped feature flags without redeploy.
        </p>
      </header>

      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <TenantSelector
          tenants={tenants}
          value={selectedTenant}
          onChange={setSelectedTenant}
        />
        <select
          value={selectedModule}
          onChange={(event) => setSelectedModule(event.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="">Select module</option>
          {modules.map((module) => (
            <option key={module.id} value={module.id}>
              {module.module_name}
            </option>
          ))}
        </select>
        <select
          value={scopeType}
          onChange={(event) => setScopeType(event.target.value as "tenant" | "user" | "entity" | "canary")}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="tenant">tenant</option>
          <option value="user">user</option>
          <option value="entity">entity</option>
          <option value="canary">canary</option>
        </select>
        <input
          value={flagKey}
          onChange={(event) => setFlagKey(event.target.value)}
          placeholder="flag key"
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        />
        <button
          type="button"
          onClick={() => void onCreate()}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground md:col-span-4"
        >
          Create Flag
        </button>
      </section>

      <DataTable
        rows={rows}
        emptyMessage="No feature flags found."
        columns={[
          { key: "key", header: "Flag", render: (row) => <span className="font-medium">{row.flag_key}</span> },
          {
            key: "module",
            header: "Module",
            render: (row) => moduleMap.get(row.module_id) ?? row.module_id,
          },
          { key: "scope", header: "Scope", render: (row) => row.target_scope_type },
          { key: "mode", header: "Mode", render: (row) => row.rollout_mode },
          {
            key: "enabled",
            header: "Enabled",
            render: (row) => (
              <ToggleSwitch
                checked={row.rollout_mode !== "off"}
                onChange={(next) => {
                  void onToggle(row, next)
                }}
              />
            ),
          },
          {
            key: "actions",
            header: "Actions",
            render: (row) => (
              <button
                type="button"
                onClick={() => {
                  void onDelete(row)
                }}
                className="rounded-md border border-[hsl(var(--brand-danger)/0.5)] px-2 py-1 text-xs text-[hsl(var(--brand-danger))]"
              >
                Delete
              </button>
            ),
          },
        ]}
      />
    </div>
  )
}
