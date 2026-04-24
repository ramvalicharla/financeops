"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import {
  bulkConfirmErpMappings,
  confirmErpMapping,
  getErpMappingSummary,
  getErpMappings,
  getTenantCoaAccounts,
  type ErpMapping,
} from "@/lib/api/coa"
import type { OrgEntity } from "@/lib/api/orgSetup"
import { queryKeys } from "@/lib/query/keys"

interface Step6ErpMappingProps {
  entities: OrgEntity[]
  submitting: boolean
  onSubmit: (payload: { confirmed_mapping_ids: string[]; auto_confirm_above?: string }) => Promise<void>
}

const confidencePercent = (value: string | null): number => {
  if (!value) {
    return 0
  }
  const parsed = Number(value)
  if (Number.isNaN(parsed)) {
    return 0
  }
  return parsed * 100
}

const badgeClass = (value: number): string => {
  if (value >= 90) {
    return "bg-[hsl(var(--brand-success)/0.15)] text-[hsl(var(--brand-success))]"
  }
  if (value >= 70) {
    return "bg-[hsl(var(--brand-warning)/0.15)] text-[hsl(var(--brand-warning))]"
  }
  return "bg-[hsl(var(--brand-danger)/0.15)] text-[hsl(var(--brand-danger))]"
}

export function Step6ErpMapping({ entities, submitting, onSubmit }: Step6ErpMappingProps) {
  const queryClient = useQueryClient()
  const [selectedEntityId, setSelectedEntityId] = useState<string>(entities[0]?.cp_entity_id ?? "")
  const [connectorType, setConnectorType] = useState("TALLY")
  const [viewFilter, setViewFilter] = useState<"all" | "unmapped" | "unconfirmed">("all")

  const tenantAccountsQuery = useQuery({
    queryKey: queryKeys.orgSetup.tenantCoaAccounts(),
    queryFn: getTenantCoaAccounts,
  })

  const mappingQuery = useQuery({
    queryKey: queryKeys.orgSetup.erpMappings(selectedEntityId, connectorType),
    queryFn: () =>
      getErpMappings({
        entity_id: selectedEntityId,
        erp_connector_type: connectorType,
      }),
    enabled: Boolean(selectedEntityId),
  })

  const summaryQuery = useQuery({
    queryKey: queryKeys.orgSetup.erpSummary(selectedEntityId, connectorType),
    queryFn: () =>
      getErpMappingSummary({
        entity_id: selectedEntityId,
        erp_connector_type: connectorType,
      }),
    enabled: Boolean(selectedEntityId),
  })

  const confirmMutation = useMutation({
    mutationFn: ({ mappingId, accountId }: { mappingId: string; accountId: string }) =>
      confirmErpMapping(mappingId, accountId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.erpMappings(selectedEntityId, connectorType) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.erpSummary(selectedEntityId, connectorType) })
    },
  })

  const bulkConfirmMutation = useMutation({
    mutationFn: (ids: string[]) =>
      bulkConfirmErpMappings({
        mapping_ids: ids,
        auto_confirm_above: "0.90",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.erpMappings(selectedEntityId, connectorType) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.orgSetup.erpSummary(selectedEntityId, connectorType) })
    },
  })

  const filteredMappings = useMemo(() => {
    const source = mappingQuery.data ?? []
    if (viewFilter === "unmapped") {
      return source.filter((item) => item.tenant_coa_account_id === null)
    }
    if (viewFilter === "unconfirmed") {
      return source.filter((item) => !item.is_confirmed)
    }
    return source
  }, [mappingQuery.data, viewFilter])

  const highConfidenceIds = useMemo(() => {
    return filteredMappings
      .filter((item) => !item.is_confirmed && confidencePercent(item.mapping_confidence) >= 90)
      .map((item) => item.id)
  }, [filteredMappings])

  const confirmedIds = useMemo(() => {
    return (mappingQuery.data ?? [])
      .filter((item) => item.is_confirmed)
      .map((item) => item.id)
  }, [mappingQuery.data])

  const unmappedCount = summaryQuery.data?.unmapped ?? 0
  const hasTenantAccounts = (tenantAccountsQuery.data?.length ?? 0) > 0
  const hasMappings = filteredMappings.length > 0
  const hasMappingError =
    tenantAccountsQuery.isError || mappingQuery.isError || summaryQuery.isError

  const handleComplete = async () => {
    await onSubmit({
      confirmed_mapping_ids: confirmedIds,
      auto_confirm_above: "0.90",
    })
  }

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">Account mapping</h2>
        <Button
          variant="outline"
          disabled={!highConfidenceIds.length || bulkConfirmMutation.isPending}
          onClick={() => bulkConfirmMutation.mutate(highConfidenceIds)}
        >
          Confirm all &gt;= 90%
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <FormField id="mapping-entity" label="Entity">
          <select
            value={selectedEntityId}
            onChange={(event) => setSelectedEntityId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select entity</option>
            {entities.map((entity) => (
              <option key={entity.id} value={entity.cp_entity_id ?? ""}>
                {entity.display_name ?? entity.legal_name}
              </option>
            ))}
          </select>
        </FormField>
        <FormField id="mapping-source" label="Source field">
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
        </FormField>
        <FormField id="mapping-transform" label="Transformation">
          <select
            value={viewFilter}
            onChange={(event) => setViewFilter(event.target.value as "all" | "unmapped" | "unconfirmed")}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="all">All</option>
            <option value="unmapped">Unmapped only</option>
            <option value="unconfirmed">Unconfirmed only</option>
          </select>
        </FormField>
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-muted-foreground">Total</p>
          <p className="font-semibold text-foreground">{summaryQuery.data?.total ?? 0}</p>
        </div>
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-muted-foreground">Mapped</p>
          <p className="font-semibold text-foreground">{summaryQuery.data?.mapped ?? 0}</p>
        </div>
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-muted-foreground">Confirmed</p>
          <p className="font-semibold text-foreground">{summaryQuery.data?.confirmed ?? 0}</p>
        </div>
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-muted-foreground">Unmapped</p>
          <p className="font-semibold text-foreground">{summaryQuery.data?.unmapped ?? 0}</p>
        </div>
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-muted-foreground">Avg confidence</p>
          <p className="font-semibold text-foreground">
            {Math.round(confidencePercent(summaryQuery.data?.confidence_avg ?? null))}%
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        {hasMappingError ? (
          <div className="p-4 text-sm text-muted-foreground">
            Mapping details will appear after you upload a chart of accounts or sync ERP data. You can finish setup now and return later.
          </div>
        ) : !hasTenantAccounts ? (
          <div className="p-4 text-sm text-muted-foreground">
            No chart of accounts is available yet. Upload it later or connect your ERP, then return here to confirm mappings.
          </div>
        ) : !hasMappings ? (
          <div className="p-4 text-sm text-muted-foreground">
            No ERP mappings were found yet. You can complete setup now and review mappings later from settings.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2">ERP account</th>
                <th className="px-3 py-2">Platform account</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredMappings.map((mapping: ErpMapping) => {
                const confidence = confidencePercent(mapping.mapping_confidence)
                return (
                  <tr key={mapping.id}>
                    <td className="px-3 py-2">
                      <p className="text-foreground">{mapping.erp_account_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{mapping.erp_account_code}</p>
                    </td>
                    <td className="px-3 py-2">
                      <FormField id={`mapping-target-${mapping.id}`} label="Target field">
                        <select
                          value={mapping.tenant_coa_account_id ?? ""}
                          onChange={(event) => {
                            if (!event.target.value) {
                              return
                            }
                            confirmMutation.mutate({
                              mappingId: mapping.id,
                              accountId: event.target.value,
                            })
                          }}
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        >
                          <option value="">Unmapped</option>
                          {(tenantAccountsQuery.data ?? []).map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.account_code} - {account.display_name}
                            </option>
                          ))}
                        </select>
                      </FormField>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs ${badgeClass(confidence)}`}>
                        {Math.round(confidence)}%
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {mapping.is_confirmed ? "Confirmed" : mapping.tenant_coa_account_id ? "Unconfirmed" : "Unmapped"}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {unmappedCount > 0 ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
          {unmappedCount} accounts are unmapped. They will be excluded from financial reports until mapped.
          You can complete mapping later in Settings -&gt; ERP Mapping.
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button onClick={() => void handleComplete()} disabled={submitting || mappingQuery.isLoading}>
          {submitting ? "Completing setup..." : "Complete setup"}
        </Button>
      </div>
    </section>
  )
}
