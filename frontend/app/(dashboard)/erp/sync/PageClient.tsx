"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import {
  listErpConnectors,
  listErpSyncJobs,
  runErpSync,
  type ErpSyncModule,
  type ErpSyncType,
} from "@/lib/api/erp"
import {
  canPerformAction,
  getAccessErrorMessage,
  getPermissionDeniedMessage,
} from "@/lib/ui-access"
import { Button } from "@/components/ui/button"

const MODULES: ErpSyncModule[] = ["COA", "JOURNALS", "VENDORS", "CUSTOMERS"]
const TYPES: ErpSyncType[] = ["IMPORT", "EXPORT"]

export default function ErpSyncPage() {
  const { data: session } = useSession()
  const queryClient = useQueryClient()
  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(session?.user?.tenant_id),
  })
  const canRunSync = canPerformAction("erp.sync.run", {
    role: session?.user?.role,
    entitlements: entitlementsQuery.data,
  })
  const [connectorId, setConnectorId] = useState("")
  const [syncType, setSyncType] = useState<ErpSyncType>("IMPORT")
  const [moduleName, setModuleName] = useState<ErpSyncModule>("COA")

  const connectorsQuery = useQuery({
    queryKey: ["erp-connectors"],
    queryFn: listErpConnectors,
  })

  const jobsQuery = useQuery({
    queryKey: ["erp-sync-jobs", connectorId],
    queryFn: () => listErpSyncJobs({ erp_connector_id: connectorId || undefined }),
  })

  const runSyncMutation = useMutation({
    mutationFn: () =>
      runErpSync({
        erp_connector_id: connectorId,
        sync_type: syncType,
        module: moduleName,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["erp-sync-jobs", connectorId] })
    },
  })

  const canRun = useMemo(() => Boolean(connectorId), [connectorId])
  const pageErrorMessage =
    connectorsQuery.error?.message ??
    jobsQuery.error?.message ??
    runSyncMutation.error?.message ??
    null
  const accessErrorMessage = getAccessErrorMessage(
    connectorsQuery.error ?? jobsQuery.error ?? runSyncMutation.error ?? null,
    "ERP Sync",
  )

  if (accessErrorMessage) {
    return (
      <div className="space-y-6 p-6">
        <section className="rounded-xl border border-border bg-card p-4">
          <h1 className="text-xl font-semibold text-foreground">ERP Sync Dashboard</h1>
        </section>
        <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">ERP Sync Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Trigger import/export jobs and monitor execution status with retry count and error traces.
        </p>
        {!canRunSync ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Only tenant administrators can trigger ERP sync runs.
          </p>
        ) : null}
      </section>

      {pageErrorMessage ? (
        <section className="rounded-xl border border-destructive/30 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{pageErrorMessage}</p>
        </section>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-4">
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
          <select
            value={syncType}
            onChange={(event) => setSyncType(event.target.value as ErpSyncType)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {TYPES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={moduleName}
            onChange={(event) => setModuleName(event.target.value as ErpSyncModule)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {MODULES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <Button
            onClick={() => runSyncMutation.mutate()}
            disabled={!canRun || runSyncMutation.isPending || !canRunSync}
            title={!canRunSync ? getPermissionDeniedMessage("erp.sync.run") : undefined}
            type="button"
          >
            {runSyncMutation.isPending ? "Running..." : "Run Sync"}
          </Button>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Job</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Module</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Retries</th>
                <th className="px-4 py-2">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(jobsQuery.data ?? []).map((job) => (
                <tr key={job.id}>
                  <td className="px-4 py-2 font-mono text-xs">{job.id}</td>
                  <td className="px-4 py-2">{job.sync_type}</td>
                  <td className="px-4 py-2">{job.module}</td>
                  <td className="px-4 py-2">{job.status}</td>
                  <td className="px-4 py-2">{job.retry_count}</td>
                  <td className="px-4 py-2 text-xs text-[hsl(var(--brand-danger))]">
                    {job.error_message ?? "-"}
                  </td>
                </tr>
              ))}
              {!jobsQuery.isLoading && !jobsQuery.data?.length && !pageErrorMessage ? (
                <tr>
                  <td className="px-4 py-6 text-center text-muted-foreground" colSpan={6}>
                    No ERP sync jobs available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
