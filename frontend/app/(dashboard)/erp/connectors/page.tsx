"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createErpConnector,
  listErpConnectors,
  testErpConnector,
  type ErpAuthType,
  type ErpConnectorStatus,
  updateErpConnectorStatus,
} from "@/lib/api/erp"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

const ERP_TYPES = ["TALLY", "ZOHO", "QUICKBOOKS", "SAP", "ORACLE", "MANUAL"] as const
const AUTH_TYPES: ErpAuthType[] = ["API_KEY", "OAUTH", "BASIC"]

export default function ErpConnectorsPage() {
  const queryClient = useQueryClient()
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const defaultEntityId = entityRoles.at(0)?.entity_id ?? ""

  const [orgEntityId, setOrgEntityId] = useState(defaultEntityId)
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
        org_entity_id: orgEntityId,
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

  const canCreate = useMemo(() => Boolean(orgEntityId), [orgEntityId])

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">ERP Connectors</h1>
        <p className="text-sm text-muted-foreground">
          Configure connector credentials, test connectivity, and manage activation state.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          New Connector
        </h2>
        <div className="grid gap-3 md:grid-cols-3">
          <select
            value={orgEntityId}
            onChange={(event) => setOrgEntityId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select entity</option>
            {entityRoles.map((entity) => (
              <option key={entity.entity_id} value={entity.entity_id}>
                {entity.entity_name}
              </option>
            ))}
          </select>
          <select
            value={erpType}
            onChange={(event) => setErpType(event.target.value as (typeof ERP_TYPES)[number])}
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
          className="mt-3 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
        />
        <div className="mt-3">
          <Button
            disabled={!canCreate || createMutation.isPending}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? "Creating..." : "Create Connector"}
          </Button>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">ERP</th>
                <th className="px-4 py-2">Entity</th>
                <th className="px-4 py-2">Auth</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(connectorsQuery.data ?? []).map((connector) => (
                <tr key={connector.id}>
                  <td className="px-4 py-2">{connector.erp_type}</td>
                  <td className="px-4 py-2 font-mono text-xs">{connector.org_entity_id}</td>
                  <td className="px-4 py-2">{connector.auth_type}</td>
                  <td className="px-4 py-2">{connector.status}</td>
                  <td className="space-x-2 px-4 py-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => testMutation.mutate(connector.id)}
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
                      type="button"
                    >
                      {connector.status === "ACTIVE" ? "Deactivate" : "Activate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {testResult ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Latest Test Result
          </h3>
          <pre className="overflow-x-auto rounded-md bg-background p-3 text-xs">
            {JSON.stringify(testResult, null, 2)}
          </pre>
        </section>
      ) : null}
    </div>
  )
}
