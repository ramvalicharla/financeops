"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveWorkspaceFromTabs } from "@/lib/control-plane"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

export function ModuleTabs() {
  const pathname = usePathname() ?? ""
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId, "workspace-tabs"],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
      }),
    staleTime: 60_000,
  })

  const visibleTabs = contextQuery.data?.workspace_tabs ?? []
  const activeModuleKey = useMemo(() => {
    const matchedTab = resolveWorkspaceFromTabs(pathname, visibleTabs)
    return matchedTab?.workspace_key ?? contextQuery.data?.current_module.module_key ?? null
  }, [contextQuery.data?.current_module.module_key, pathname, visibleTabs])
  const activeLabel = useMemo(() => {
    const activeTab = visibleTabs.find((tab) => tab.workspace_key === activeModuleKey)
    return activeTab?.workspace_name ?? contextQuery.data?.current_module.module_name ?? "Unavailable"
  }, [activeModuleKey, contextQuery.data?.current_module.module_name, visibleTabs])

  return (
    <div className="border-b border-border bg-background/90 px-4 md:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Workspace Modules
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {contextQuery.isLoading
              ? "Waiting for backend module context."
              : `Tabs are rendered from backend workspace context. Backend workspace: ${contextQuery.data?.current_module.module_name ?? "Unavailable"}.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            {visibleTabs.length} visible
          </span>
          <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            Viewing: {activeLabel}
          </span>
        </div>
      </div>
      <nav aria-label="Module tabs" className="flex gap-2 overflow-x-auto pb-4">
        {visibleTabs.map((tab) => {
          const isActive = tab.workspace_key === activeModuleKey
          return (
            <Link
              key={tab.workspace_key}
              href={tab.href}
              className={cn(
                "rounded-full border px-4 py-2 text-sm transition-colors",
                isActive
                  ? "border-foreground bg-foreground text-background shadow-sm"
                  : "border-border bg-card text-muted-foreground hover:border-[hsl(var(--brand-primary)/0.3)] hover:text-foreground",
              )}
            >
              {tab.workspace_name}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
