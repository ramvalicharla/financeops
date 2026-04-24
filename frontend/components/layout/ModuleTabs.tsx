"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveWorkspaceFromTabs } from "@/lib/control-plane"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

// Prevents blank tab bar if backend omits workspace_tabs. See audit QW-0.
const FALLBACK_TABS = [
  { workspace_key: "overview", workspace_name: "Overview", href: "/dashboard" },
]

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

  const tabs = contextQuery.data?.workspace_tabs?.length
    ? contextQuery.data.workspace_tabs
    : FALLBACK_TABS
  const visibleTabs = tabs
  const activeModuleKey = useMemo(() => {
    const matchedTab = resolveWorkspaceFromTabs(pathname, visibleTabs)
    return matchedTab?.workspace_key ?? contextQuery.data?.current_module.module_key ?? null
  }, [contextQuery.data?.current_module.module_key, pathname, visibleTabs])
  return (
    <div className="border-b border-border bg-background/90 px-4 md:px-6">
      <nav aria-label="Module tabs" className="flex gap-0 overflow-x-auto">
        {visibleTabs.map((tab) => {
          const isActive = tab.workspace_key === activeModuleKey
          return (
            <Link
              key={tab.workspace_key}
              href={tab.href}
              className={cn(
                "whitespace-nowrap px-4 py-2.5 text-sm transition-colors border-b-2",
                isActive
                  ? "border-[#185FA5] font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
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
