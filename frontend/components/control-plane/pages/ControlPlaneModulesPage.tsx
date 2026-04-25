"use client"

import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { Button } from "@/components/ui/button"

export function ControlPlaneModulesPage() {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const contextQuery = useQuery({
    queryKey: controlPlaneQueryKeys.context({ entity_id: activeEntityId ?? undefined }),
    queryFn: () => getControlPlaneContext({ entity_id: activeEntityId ?? undefined }),
  })

  return (
    <PageScaffold
      title="Modules"
      description="Backend-driven module capability rendering for the current tenant and entity scope."
    >
      <section className="rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Capability matrix</h2>
            <p className="text-sm text-muted-foreground">
              Enabled modules are rendered from backend context. Dependency and guard detail remain limited by the current contract.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void contextQuery.refetch()}>
            Refresh
          </Button>
        </div>

        <div className="mt-4 overflow-x-auto rounded-xl border border-border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Module</th>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Engine Context</th>
                <th className="px-4 py-2">Financial Impact</th>
                <th className="px-4 py-2">Contract Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(contextQuery.data?.enabled_modules ?? []).map((module) => (
                <tr key={module.module_id}>
                  <td className="px-4 py-2 text-foreground">{module.module_name}</td>
                  <td className="px-4 py-2 text-muted-foreground">{module.module_code}</td>
                  <td className="px-4 py-2 text-muted-foreground">{module.engine_context}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {module.is_financial_impacting ? "Yes" : "No"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    Dependency and guard detail unavailable in current contract
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!contextQuery.data?.enabled_modules.length ? (
          <p className="mt-4 text-sm text-muted-foreground">
            No enabled modules were returned by the backend for this scope.
          </p>
        ) : null}
      </section>
    </PageScaffold>
  )
}
