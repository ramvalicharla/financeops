"use client"

import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useMemo } from "react"
import { Lock, Plus } from "lucide-react"
import * as Sentry from "@sentry/browser"
import { useQuery } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveWorkspaceFromTabs } from "@/lib/control-plane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"
import { getModuleIcon } from "@/components/layout/tabs/module-icons"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import { canPerformAction } from "@/lib/ui-access"
import { useModuleManagerStore } from "@/lib/store/moduleManager"
import { ModuleManager } from "@/components/modules/ModuleManager"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

// Prevents blank tab bar if backend omits workspace_tabs. See audit QW-0.
const FALLBACK_TABS = [
  { workspace_key: "dashboard", workspace_name: "Dashboard", href: "/dashboard", match_prefixes: ["/dashboard"], module_codes: [] },
]

export function ModuleTabs() {
  const pathname = usePathname() ?? ""
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const { data: session } = useSession()
  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(session?.user?.tenant_id),
  })
  const openModuleManager = useModuleManagerStore((s) => s.open)
  const router = useRouter()
  const searchParams = useSearchParams()

  // Open modal when redirected from /settings/modules (OQ-1 REDIRECT).
  // Cleans the param from the URL after opening so refresh doesn't re-trigger.
  useEffect(() => {
    if (searchParams.get("modal") === "module-manager") {
      openModuleManager()
      const params = new URLSearchParams(searchParams.toString())
      params.delete("modal")
      const clean = params.size > 0 ? `?${params.toString()}` : window.location.pathname
      router.replace(clean, { scroll: false })
    }
  }, [searchParams, openModuleManager, router])

  const contextQuery = useQuery({
    queryKey: queryKeys.workspace.tabs(activeEntityId),
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
      }),
    staleTime: 60_000,
  })

  const tabs = contextQuery.data?.workspace_tabs?.length
    ? contextQuery.data.workspace_tabs
    : FALLBACK_TABS

  // Spec §1.5: Dashboard must be first and required. Re-sort if backend violates this.
  const visibleTabs = (() => {
    if (tabs[0]?.workspace_key === "dashboard") return tabs
    const dashboard = tabs.find((t) => t.workspace_key === "dashboard")
    const others = tabs.filter((t) => t.workspace_key !== "dashboard")
    if (!dashboard) {
      Sentry.captureMessage("[shell] Backend omitted Dashboard tab; prepending from fallback.", "warning")
      return [{ workspace_key: "dashboard", workspace_name: "Dashboard", href: "/dashboard", match_prefixes: ["/dashboard"], module_codes: [] }, ...others]
    }
    Sentry.captureMessage("[shell] Backend returned non-canonical tab order; re-sorting to put Dashboard first.", "warning")
    return [dashboard, ...others]
  })()

  const activeModuleKey = useMemo(() => {
    const matchedTab = resolveWorkspaceFromTabs(pathname, visibleTabs)
    return matchedTab?.workspace_key ?? contextQuery.data?.current_module.module_key ?? null
  }, [contextQuery.data?.current_module.module_key, pathname, visibleTabs])

  // TODO(module.manage): Backend ticket pending. canPerformAction returns false for all
  // users until backend RBAC system + PERMISSIONS matrix entry land.
  // See docs/tickets/module-manage-permission.md (to be filed).
  const canManageModules = canPerformAction("module.manage", {
    role: session?.user?.role,
    entitlements: entitlementsQuery.data,
  })

  return (
    <>
      <div className="h-10 border-b border-border bg-background/90 px-4 md:px-6">
        <nav aria-label="Module tabs" className="flex h-full gap-0 overflow-x-auto">
          {visibleTabs.map((tab) => {
            const isActive = tab.workspace_key === activeModuleKey
            const Icon = getModuleIcon(tab.workspace_key)
            return (
              <Link
                key={tab.workspace_key}
                href={tab.href}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap px-4 py-2.5 text-sm transition-colors border-b-2",
                  isActive
                    ? "border-[#185FA5] font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon size={14} className="shrink-0" />
                <span>{tab.workspace_name}</span>
              </Link>
            )
          })}

          {canManageModules ? (
            <button
              type="button"
              onClick={openModuleManager}
              aria-label="Open Module Manager"
              className="ml-1.5 my-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-dashed border-muted-foreground/50 text-sm text-muted-foreground transition-colors hover:border-foreground/50 hover:text-foreground"
            >
              <Plus size={14} aria-hidden="true" />
            </button>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  disabled
                  aria-label="Ask your admin to enable module management"
                  className="ml-1.5 my-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-dashed border-muted-foreground/30 text-sm text-muted-foreground/50 cursor-not-allowed"
                >
                  <Lock size={12} aria-hidden="true" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Ask your admin to enable module management</TooltipContent>
            </Tooltip>
          )}
        </nav>
      </div>

      {/* ModuleManager portal renders to document.body — placement here is arbitrary */}
      <ModuleManager />
    </>
  )
}
