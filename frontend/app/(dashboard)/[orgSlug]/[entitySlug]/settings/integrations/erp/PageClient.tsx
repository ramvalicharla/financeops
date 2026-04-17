"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import {
  createErpConnector,
  listErpConnectors,
  testErpConnector,
  type ErpAuthType,
  type ErpConnectorStatus,
  updateErpConnectorStatus,
} from "@/lib/api/erp"
import { useTenantStore } from "@/lib/store/tenant"
import {
  canPerformAction,
  getAccessErrorMessage,
  getPermissionDeniedMessage,
} from "@/lib/ui-access"
import { StructuredDataView } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { DataGrid } from "@/components/ui/data-grid"
import type { ColumnDef } from "@tanstack/react-table"

const ERP_TYPES = ["TALLY", "ZOHO", "QUICKBOOKS", "SAP", "ORACLE", "MANUAL"] as const
const AUTH_TYPES: ErpAuthType[] = ["API_KEY", "OAUTH", "BASIC"]

export default function ErpConnectorsPage() {
  const { data: session } = useSession()
  const queryClient = useQueryClient()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(session?.user?.tenant_id),
  })
  const accessContext = {
    role: session?.user?.role,
    entitlements: entitlementsQuery.data,
  }
  const canCreateConnector = canPerformAction(
    "erp.connectors.create",
    accessContext,
  )
  const canUpdateConnector = canPerformAction(
    "erp.connectors.update",
    accessContext,
  )


  const [erpType, setErpType] = useState<(typeof ERP_TYPES)[number]>("TALLY")
  const [authType, setAuthType] = useState<ErpAuthType>("API_KEY")
  const [credentialsJson, setCredentialsJson] = useState("{\n  \"api_key\": \"\"\n}")
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null)

  const connectorsQuery = useQuery({
    queryKey: ["erp-connectors"],
    queryFn: listErpConnectors,
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      let credentials: Record<string, unknown> = {}
      try {
        const parsed = JSON.parse(credentialsJson)
        credentials = typeof parsed === "object" && parsed ? parsed : {}
      } catch {
        credentials = {}
      }
      return createErpConnector({
        org_entity_id: activeEntityId ?? "",
        erp_type: erpType,
        auth_type: authType,
        connection_config: { credentials },
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["erp-connectors"] })
    },
  })

  const testMutation = useMutation({
    mutationFn: (connectorId: string) => testErpConnector(connectorId),
    onSuccess: (result) => setTestResult(result.result),
  })

  const statusMutation = useMutation({
    mutationFn: ({ connectorId, status }: { connectorId: string; status: ErpConnectorStatus }) =>
      updateErpConnectorStatus(connectorId, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["erp-connectors"] })
    },
  })

  const canCreate = useMemo(() => Boolean(activeEntityId), [activeEntityId])
  const pageErrorMessage =
    connectorsQuery.error?.message ??
    createMutation.error?.message ??
    testMutation.error?.message ??
    statusMutation.error?.message ??
    null

  const columns = useMemo<ColumnDef<any>[]>(
    () => [
      {
        accessorKey: "erp_type",
        header: "ERP",
      },
      {
        accessorKey: "org_entity_id",
        header: "Entity",
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.org_entity_id}</span>,
      },
      {
        accessorKey: "auth_type",
        header: "Auth",
      },
      {
        accessorKey: "status",
        header: "Status",
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const connector = row.original
          return (
            <div className="space-x-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => testMutation.mutate(connector.id)}
                disabled={!canUpdateConnector}
                title={!canUpdateConnector ? getPermissionDeniedMessage("erp.connectors.update") : undefined}
                type="button"
              >
                Test
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  statusMutation.mutate({
                    connectorId: connector.id,
                    status: connector.status === "ACTIVE" ? "INACTIVE" : "ACTIVE",
                  })
                }
                disabled={!canUpdateConnector}
                title={!canUpdateConnector ? getPermissionDeniedMessage("erp.connectors.update") : undefined}
                type="button"
              >
                {connector.status === "ACTIVE" ? "Deactivate" : "Activate"}
              </Button>
            </div>
          )
        },
      },
    ],
    [canUpdateConnector, testMutation, statusMutation]
  )

  const accessErrorMessage = getAccessErrorMessage(
    connectorsQuery.error ??
      createMutation.error ??
      testMutation.error ??
      statusMutation.error ??
      null,
    "ERP Connectors",
  )

  if (accessErrorMessage) {
    return (
      <div className="space-y-6 p-6">
        <section className="rounded-xl border border-border bg-card p-4">
          <h1 className="text-xl font-semibold text-foreground">ERP Connectors</h1>
        </section>
        <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">ERP Connectors</h1>
        <p className="text-sm text-muted-foreground">
          Configure connector credentials, test connectivity, and manage activation state.
        </p>
        {!canCreateConnector ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Only tenant administrators can create or modify ERP connectors.
          </p>
        ) : null}
      </section>

      {pageErrorMessage ? (
        <section className="rounded-xl border border-destructive/30 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{pageErrorMessage}</p>
        </section>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          New Connector
        </h2>
        <div className="grid gap-3 md:grid-cols-3">

          <select
            value={erpType}
            onChange={(event) => setErpType(event.target.value as (typeof ERP_TYPES)[number])}
            disabled={!canCreateConnector}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {ERP_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <select
            value={authType}
            onChange={(event) => setAuthType(event.target.value as ErpAuthType)}
            disabled={!canCreateConnector}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {AUTH_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <textarea
          value={credentialsJson}
          onChange={(event) => setCredentialsJson(event.target.value)}
          rows={7}
          disabled={!canCreateConnector}
          className="mt-3 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
        />
        <div className="mt-3">
          <Button
            disabled={!canCreate || createMutation.isPending || !canCreateConnector}
            title={!canCreateConnector ? getPermissionDeniedMessage("erp.connectors.create") : undefined}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? "Creating..." : "Create Connector"}
          </Button>
        </div>
      </section>

      <section>
        <DataGrid 
          columns={columns} 
          data={connectorsQuery.data ?? []} 
        />
      </section>

      </section>

      {testResult ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Latest Test Result
          </h3>
          <StructuredDataView
            data={testResult}
            emptyMessage="No structured test result is available."
          />
        </section>
      ) : null}
    </div>
  )
}
