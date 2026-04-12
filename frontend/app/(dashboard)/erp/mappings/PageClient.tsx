"use client"

import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  exportErpJournals,
  importErpCoa,
  importErpJournals,
  listErpConnectors,
  mapErpCoa,
  syncErpCustomers,
  syncErpVendors,
} from "@/lib/api/erp"
import { getTenantCoaAccounts } from "@/lib/api/coa"
import { StructuredDataView } from "@/components/ui"
import { Button } from "@/components/ui/button"

export default function ErpMappingsPage() {
  const [connectorId, setConnectorId] = useState("")
  const [erpAccountId, setErpAccountId] = useState("")
  const [internalAccountId, setInternalAccountId] = useState("")
  const [resultPayload, setResultPayload] = useState<Record<string, unknown> | null>(null)

  const connectorsQuery = useQuery({
    queryKey: ["erp-connectors"],
    queryFn: listErpConnectors,
  })

  const accountsQuery = useQuery({
    queryKey: ["tenant-coa-accounts-for-erp-mapping"],
    queryFn: getTenantCoaAccounts,
  })

  const coaImportMutation = useMutation({
    mutationFn: () => importErpCoa(connectorId),
    onSuccess: (payload) => setResultPayload(payload),
  })

  const coaMapMutation = useMutation({
    mutationFn: () =>
      mapErpCoa({
        erp_connector_id: connectorId,
        mappings: [{ erp_account_id: erpAccountId, internal_account_id: internalAccountId }],
      }),
    onSuccess: (payload) => setResultPayload(payload),
  })

  const importJournalsMutation = useMutation({
    mutationFn: () => importErpJournals({ erp_connector_id: connectorId }),
    onSuccess: (payload) => setResultPayload(payload),
  })

  const exportJournalsMutation = useMutation({
    mutationFn: () => exportErpJournals({ erp_connector_id: connectorId }),
    onSuccess: (payload) => setResultPayload(payload),
  })

  const vendorsMutation = useMutation({
    mutationFn: () => syncErpVendors({ erp_connector_id: connectorId }),
    onSuccess: (payload) => setResultPayload(payload),
  })

  const customersMutation = useMutation({
    mutationFn: () => syncErpCustomers({ erp_connector_id: connectorId }),
    onSuccess: (payload) => setResultPayload(payload),
  })
  const pageErrorMessage =
    connectorsQuery.error?.message ??
    accountsQuery.error?.message ??
    coaImportMutation.error?.message ??
    coaMapMutation.error?.message ??
    importJournalsMutation.error?.message ??
    exportJournalsMutation.error?.message ??
    vendorsMutation.error?.message ??
    customersMutation.error?.message ??
    null

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">ERP Mappings</h1>
        <p className="text-sm text-muted-foreground">
          Import and map ERP chart-of-accounts, then trigger journal/vendor/customer sync actions.
        </p>
      </section>

      {pageErrorMessage ? (
        <section className="rounded-xl border border-destructive/30 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{pageErrorMessage}</p>
        </section>
      ) : null}

      {!accountsQuery.isLoading &&
      !accountsQuery.isError &&
      (accountsQuery.data?.length ?? 0) === 0 ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            No chart of accounts is available yet. Upload it later or connect your ERP before creating internal mappings.
          </p>
        </section>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <select
            value={connectorId}
            onChange={(event) => setConnectorId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select connector</option>
            {(connectorsQuery.data ?? []).map((connector) => (
              <option key={connector.id} value={connector.id}>
                {connector.erp_type} ({connector.org_entity_id.slice(0, 8)})
              </option>
            ))}
          </select>
          <input
            value={erpAccountId}
            onChange={(event) => setErpAccountId(event.target.value)}
            placeholder="ERP account id"
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <select
            value={internalAccountId}
            onChange={(event) => setInternalAccountId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select internal account</option>
            {(accountsQuery.data ?? []).map((account) => (
              <option key={account.id} value={account.id}>
                {account.account_code} - {account.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            onClick={() => coaImportMutation.mutate()}
            disabled={!connectorId || coaImportMutation.isPending}
            type="button"
          >
            Import COA
          </Button>
          <Button
            variant="outline"
            onClick={() => coaMapMutation.mutate()}
            disabled={!connectorId || !erpAccountId || !internalAccountId || coaMapMutation.isPending}
            type="button"
          >
            Map COA Account
          </Button>
          <Button
            variant="outline"
            onClick={() => importJournalsMutation.mutate()}
            disabled={!connectorId || importJournalsMutation.isPending}
            type="button"
          >
            Import Journals
          </Button>
          <Button
            variant="outline"
            onClick={() => exportJournalsMutation.mutate()}
            disabled={!connectorId || exportJournalsMutation.isPending}
            type="button"
          >
            Export Journals
          </Button>
          <Button
            variant="outline"
            onClick={() => vendorsMutation.mutate()}
            disabled={!connectorId || vendorsMutation.isPending}
            type="button"
          >
            Sync Vendors
          </Button>
          <Button
            variant="outline"
            onClick={() => customersMutation.mutate()}
            disabled={!connectorId || customersMutation.isPending}
            type="button"
          >
            Sync Customers
          </Button>
        </div>
      </section>

      {resultPayload ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Latest Operation Result
          </h3>
          <StructuredDataView
            data={resultPayload}
            emptyMessage="No structured operation result is available."
          />
        </section>
      ) : null}
    </div>
  )
}
