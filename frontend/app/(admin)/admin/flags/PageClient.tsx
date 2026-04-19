"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { DataTable } from "@/components/admin/DataTable"
import { TenantSelector } from "@/components/admin/TenantSelector"
import { ToggleSwitch } from "@/components/admin/ToggleSwitch"
import { FormField } from "@/components/ui/FormField"
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
import { canPerformAction, getPermissionDeniedMessage } from "@/lib/ui-access"
import { toast } from "sonner"

const nowIso = () => new Date().toISOString()

export default function AdminFlagsPage() {
  const { data: session } = useSession()
  const canCreateFlags = canPerformAction("platform.flags.create", session?.user?.role)
  const canUpdateFlags = canPerformAction("platform.flags.update", session?.user?.role)
  const canDeleteFlags = canPerformAction("platform.flags.delete", session?.user?.role)
  const [rows, setRows] = useState<PlatformFeatureFlag[]>([])
  const [tenants, setTenants] = useState<PlatformTenant[]>([])
  const [modules, setModules] = useState<ServiceRegistryModule[]>([])
  const [selectedTenant, setSelectedTenant] = useState("")
  const [selectedModule, setSelectedModule] = useState("")
  const [flagKey, setFlagKey] = useState("")
  const [scopeType, setScopeType] = useState<"tenant" | "user" | "entity" | "canary">("tenant")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    tenant?: string
    module?: string
    scope?: string
    flagKey?: string
  }>({})
  
  const load = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load])

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
    const nextFieldErrors: typeof fieldErrors = {}
    if (!selectedTenant) nextFieldErrors.tenant = "Tenant is required."
    if (!selectedModule) nextFieldErrors.module = "Module is required."
    if (!scopeType) nextFieldErrors.scope = "Scope is required."
    if (!flagKey.trim()) nextFieldErrors.flagKey = "Flag key is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      setError(null)
      return
    }
    setFieldErrors({})
    setError(null)
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
      toast.success("Feature flag created.")
      const items = await listFeatureFlags({ tenant_id: selectedTenant })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create feature flag")
    }
  }

  const onToggle = async (row: PlatformFeatureFlag, enabled: boolean) => {
    setError(null)
        try {
      await updateFeatureFlag(row.id, { enabled })
      toast.success(`Flag ${row.flag_key} ${enabled ? "enabled" : "disabled"}.`)
      const items = await listFeatureFlags({ tenant_id: selectedTenant || undefined })
      setRows(items)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update feature flag")
    }
  }

  const onDelete = async (row: PlatformFeatureFlag) => {
    setError(null)
        try {
      await deleteFeatureFlag(row.id)
      toast.success(`Flag ${row.flag_key} deleted.`)
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
        {!canUpdateFlags ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Only platform owners can create, toggle, or delete feature flags.
          </p>
        ) : null}
      </header>

            {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <TenantSelector
          id="flag-tenant"
          label="Tenant"
          error={fieldErrors.tenant}
          required
          tenants={tenants}
          value={selectedTenant}
          onChange={setSelectedTenant}
        />
        <FormField id="flag-module" label="Module" error={fieldErrors.module} required>
          <select
            value={selectedModule}
            onChange={(event) => setSelectedModule(event.target.value)}
            disabled={!canCreateFlags}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select module</option>
            {modules.map((module) => (
              <option key={module.id} value={module.id}>
                {module.module_name}
              </option>
            ))}
          </select>
        </FormField>
        <FormField id="flag-scope" label="Scope" error={fieldErrors.scope} required>
          <select
            value={scopeType}
            onChange={(event) => setScopeType(event.target.value as "tenant" | "user" | "entity" | "canary")}
            disabled={!canCreateFlags}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="tenant">tenant</option>
            <option value="user">user</option>
            <option value="entity">entity</option>
            <option value="canary">canary</option>
          </select>
        </FormField>
        <FormField id="flag-key" label="Flag key" error={fieldErrors.flagKey} required>
          <input
            value={flagKey}
            onChange={(event) => setFlagKey(event.target.value)}
            placeholder="flag key"
            disabled={!canCreateFlags}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <button
          type="button"
          onClick={() => void onCreate()}
          disabled={!canCreateFlags}
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
                disabled={!canUpdateFlags}
                title={!canUpdateFlags ? getPermissionDeniedMessage("platform.flags.update") : undefined}
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
                disabled={!canDeleteFlags}
                title={!canDeleteFlags ? getPermissionDeniedMessage("platform.flags.delete") : undefined}
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
