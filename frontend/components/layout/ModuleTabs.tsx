"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { CONTROL_PLANE_MODULE_TABS, resolveControlPlaneModule } from "@/lib/control-plane"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

const MODULE_TAB_REGISTRY: Record<string, string[]> = {
  dashboard: [],
  erp: ["erp_sync"],
  accounting: ["accounting_layer", "fixed_assets", "prepaid", "gst"],
  reconciliation: ["reconciliation_bridge", "payroll_gl_normalization", "bank_reconciliation"],
  close: ["monthend", "multi_entity_consolidation", "closing_checklist"],
  reports: [
    "custom_report_builder",
    "board_pack_generator",
    "board_pack_narrative_engine",
    "mis_manager",
  ],
  settings: [],
}

export function ModuleTabs() {
  const pathname = usePathname() ?? ""
  const activeModule = resolveControlPlaneModule(pathname)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId, activeModule.key],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
        workspace: activeModule.key,
        module: activeModule.key,
      }),
    staleTime: 60_000,
  })

  const enabledModuleCodes = useMemo(
    () => new Set((contextQuery.data?.enabled_modules ?? []).map((item) => item.module_code)),
    [contextQuery.data?.enabled_modules],
  )
  const visibleTabs = useMemo(
    () => {
      if (!contextQuery.data) {
        return []
      }
      return CONTROL_PLANE_MODULE_TABS.filter((tab) => {
        const requiredCodes = MODULE_TAB_REGISTRY[tab.key] ?? []
        return requiredCodes.length === 0 || requiredCodes.some((code) => enabledModuleCodes.has(code))
      })
    },
    [contextQuery.data, enabledModuleCodes],
  )

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
              : `Tabs are filtered by backend-enabled modules. Backend workspace: ${contextQuery.data?.current_module.module_name ?? "Unavailable"}.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            {visibleTabs.length} visible
          </span>
          <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            Viewing: {activeModule.label}
          </span>
        </div>
      </div>
      <nav aria-label="Module tabs" className="flex gap-2 overflow-x-auto pb-4">
        {visibleTabs.map((tab) => {
          const isActive = tab.key === activeModule.key
          return (
            <Link
              key={tab.key}
              href={tab.href}
              className={cn(
                "rounded-full border px-4 py-2 text-sm transition-colors",
                isActive
                  ? "border-foreground bg-foreground text-background shadow-sm"
                  : "border-border bg-card text-muted-foreground hover:border-[hsl(var(--brand-primary)/0.3)] hover:text-foreground",
              )}
            >
              {tab.label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
