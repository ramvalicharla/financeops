"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  autoSuggestErpMappings,
  bulkConfirmErpMappings,
  confirmErpMapping,
  getErpMappingSummary,
  getErpMappings,
  getTenantCoaAccounts,
  type ErpMapping,
} from "@/lib/api/coa"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"

const confidenceToPercent = (value: string | null): number => {
  if (!value) {
    return 0
  }
  const asNumber = Number(value)
  if (Number.isNaN(asNumber)) {
    return 0
  }
  return asNumber * 100
}

const confidenceBadgeClass = (percent: number): string => {
  if (percent >= 90) {
    return "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
  }
  if (percent >= 70) {
    return "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]"
  }
  return "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
}

export default function ErpMappingPage() {
  const queryClient = useQueryClient()
  const entityId = useWorkspaceStore((s) => s.entityId)
  const entityRoles = useTenantStore((state) => state.entity_roles)

  const [connectorType, setConnectorType] = useState("TALLY")
  const [viewFilter, setViewFilter] = useState<"all" | "unmapped" | "unconfirmed">("all")

  const tenantAccountsQuery = useQuery({
    queryKey: queryKeys.coa.tenantAccountsForMapping(),
    queryFn: getTenantCoaAccounts,
  })

  const mappingsQuery = useQuery({
    queryKey: queryKeys.erp.mappings(entityId, connectorType),
    queryFn: () =>
      getErpMappings({
        entity_id: entityId ?? "",
        erp_connector_type: connectorType,
      }),
    enabled: Boolean(entityId),
  })

  const summaryQuery = useQuery({
    queryKey: queryKeys.erp.mappingsSummary(entityId, connectorType),
    queryFn: () =>
      getErpMappingSummary({
        entity_id: entityId ?? "",
        erp_connector_type: connectorType,
      }),
    enabled: Boolean(entityId),
  })

  const autoSuggestMutation = useMutation({
    mutationFn: async () => {
      if (!entityId) {
        return []
      }
      const accounts = (tenantAccountsQuery.data ?? []).slice(0, 25)
      return autoSuggestErpMappings({
        entity_id: entityId,
        erp_connector_type: connectorType,
        erp_accounts: accounts.map((account) => ({
          code: account.account_code,
          name: account.display_name,
          type: account.bs_pl_flag?.toLowerCase() ?? null,
        })),
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappings(entityId, connectorType) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappingsSummary(entityId, connectorType) })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: ({ mappingId, tenantCoaAccountId }: { mappingId: string; tenantCoaAccountId: string }) =>
      confirmErpMapping(mappingId, tenantCoaAccountId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappings(entityId, connectorType) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappingsSummary(entityId, connectorType) })
    },
  })

  const bulkConfirmMutation = useMutation({
    mutationFn: async (mappingIds: string[]) =>
      bulkConfirmErpMappings({
        mapping_ids: mappingIds,
        auto_confirm_above: "0.90",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappings(entityId, connectorType) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.erp.mappingsSummary(entityId, connectorType) })
    },
  })

  const filteredMappings = useMemo(() => {
    const source = mappingsQuery.data ?? []
    if (viewFilter === "unmapped") {
      return source.filter((item) => item.tenant_coa_account_id === null)
    }
    if (viewFilter === "unconfirmed") {
      return source.filter((item) => !item.is_confirmed)
    }
    return source
  }, [mappingsQuery.data, viewFilter])

  const confirmableHighConfidenceIds = useMemo(() => {
    return filteredMappings
      .filter((item) => !item.is_confirmed && confidenceToPercent(item.mapping_confidence) >= 90)
      .map((item) => item.id)
  }, [filteredMappings])

  const accountOptions = tenantAccountsQuery.data ?? []
  const isLoading = mappingsQuery.isLoading || summaryQuery.isLoading
  const hasAccounts = accountOptions.length > 0
  const hasMappings = filteredMappings.length > 0

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">ERP Account Mapping</h1>
          <p className="text-sm text-muted-foreground">
            Confirm crosswalk mappings from ERP accounts to tenant CoA accounts.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => autoSuggestMutation.mutate()}
            disabled={!entityId || autoSuggestMutation.isPending}
          >
            Auto-Suggest
          </Button>
          <Button
            onClick={() => bulkConfirmMutation.mutate(confirmableHighConfidenceIds)}
            disabled={!confirmableHighConfidenceIds.length || bulkConfirmMutation.isPending}
          >
            Confirm all &gt;= 90%
          </Button>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-5">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Total</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summaryQuery.data?.total ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Mapped</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summaryQuery.data?.mapped ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Confirmed</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summaryQuery.data?.confirmed ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Unmapped</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summaryQuery.data?.unmapped ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Avg Confidence</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">
            {Math.round(confidenceToPercent(summaryQuery.data?.confidence_avg ?? null))}%
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <select
            value={entityId ?? ""}
            onChange={(event) => useWorkspaceStore.getState().switchEntity(event.target.value || null)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select entity</option>
            {entityRoles.map((role) => (
              <option key={role.entity_id} value={role.entity_id}>
                {role.entity_name}
              </option>
            ))}
          </select>
          <select
            value={connectorType}
            onChange={(event) => setConnectorType(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="TALLY">Tally</option>
            <option value="ZOHO">Zoho</option>
            <option value="QUICKBOOKS">QuickBooks</option>
            <option value="NETSUITE">NetSuite</option>
            <option value="MANUAL">Manual</option>
          </select>
          <select
            value={viewFilter}
            onChange={(event) => setViewFilter(event.target.value as "all" | "unmapped" | "unconfirmed")}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="all">All</option>
            <option value="unmapped">Unmapped only</option>
            <option value="unconfirmed">Unconfirmed only</option>
          </select>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : !hasAccounts ? (
          <div className="p-4 text-sm text-muted-foreground">
            No chart of accounts is available yet. Upload it later or connect your ERP, then return here to confirm mappings.
          </div>
        ) : !hasMappings ? (
          <div className="p-4 text-sm text-muted-foreground">
            No ERP mappings are available yet for this entity. Run sync later and return when you have data to map.
          </div>
        ) : mappingsQuery.error ? (
          <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">
            Failed to load mapping data.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label="ERP mapping" className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">ERP Account</th>
                  <th scope="col" className="px-4 py-2">Suggested Platform Account</th>
                  <th scope="col" className="px-4 py-2">Confidence</th>
                  <th scope="col" className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredMappings.map((mapping) => {
                  const confidence = confidenceToPercent(mapping.mapping_confidence)
                  return (
                    <tr key={mapping.id}>
                      <td className="px-4 py-2">
                        <p className="font-medium text-foreground">{mapping.erp_account_name}</p>
                        <p className="font-mono text-xs text-muted-foreground">{mapping.erp_account_code}</p>
                      </td>
                      <td className="px-4 py-2">
                        <select
                          value={mapping.tenant_coa_account_id ?? ""}
                          onChange={(event) => {
                            const nextValue = event.target.value
                            if (!nextValue) {
                              return
                            }
                            confirmMutation.mutate({
                              mappingId: mapping.id,
                              tenantCoaAccountId: nextValue,
                            })
                          }}
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        >
                          <option value="">Unmapped</option>
                          {accountOptions.map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.account_code} - {account.display_name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <span className={`rounded-full px-2 py-1 text-xs ${confidenceBadgeClass(confidence)}`}>
                          {Math.round(confidence)}%
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        {mapping.is_confirmed ? (
                          <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300">
                            Confirmed
                          </span>
                        ) : mapping.tenant_coa_account_id ? (
                          <span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs text-amber-300">
                            Unconfirmed
                          </span>
                        ) : (
                          <span className="rounded-full bg-rose-500/15 px-2 py-1 text-xs text-rose-300">
                            Unmapped
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
