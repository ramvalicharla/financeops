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
  { workspace_key: "overview", workspace_name: "Overview", href: "/dashboard", match_prefixes: ["/dashboard"], module_codes: [] },
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

  // Spec §1.5: Overview must be first and required. Re-sort if backend violates this.
  const visibleTabs = (() => {
    if (tabs[0]?.workspace_key === "overview") return tabs
    const overview = tabs.find((t) => t.workspace_key === "overview")
    const others = tabs.filter((t) => t.workspace_key !== "overview")
    if (!overview) {
      console.warn("[shell] Backend omitted Overview tab; prepending from fallback.")
      return [{ workspace_key: "overview", workspace_name: "Overview", href: "/dashboard", match_prefixes: ["/dashboard"], module_codes: [] }, ...others]
    }
    console.warn("[shell] Backend returned non-canonical tab order; re-sorting to put Overview first.")
    return [overview, ...others]
  })()
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
        {/* Module Manager entry point — wired in Phase 3. See audit QW-6. */}
        <button
          type="button"
          disabled
          title="Module Manager — coming soon"
          aria-label="Module Manager — coming soon"
          className="ml-1.5 my-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-dashed border-muted-foreground/30 text-sm text-muted-foreground/50 cursor-not-allowed"
        >
          +
        </button>
      </nav>
    </div>
  )
}
