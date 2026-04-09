"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { CONTROL_PLANE_MODULE_TABS, resolveControlPlaneModule } from "@/lib/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
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
  const setCurrentModule = useControlPlaneStore((state) => state.setCurrentModule)
  const activeModule = resolveControlPlaneModule(pathname)
  const contextQuery = useQuery({
    queryKey: ["control-plane-context"],
    queryFn: getControlPlaneContext,
    staleTime: 60_000,
  })

  const enabledModuleCodes = useMemo(
    () => new Set((contextQuery.data?.enabled_modules ?? []).map((item) => item.module_code)),
    [contextQuery.data?.enabled_modules],
  )
  const visibleTabs = useMemo(
    () =>
      CONTROL_PLANE_MODULE_TABS.filter((tab) => {
        const requiredCodes = MODULE_TAB_REGISTRY[tab.key] ?? []
        return requiredCodes.length === 0 || requiredCodes.some((code) => enabledModuleCodes.has(code))
      }),
    [enabledModuleCodes],
  )

  useEffect(() => {
    setCurrentModule(activeModule.label)
  }, [activeModule.label, setCurrentModule])

  return (
    <div className="border-b border-border bg-background/90 px-4 md:px-6">
      <nav aria-label="Module tabs" className="flex gap-2 overflow-x-auto py-3">
        {visibleTabs.map((tab) => {
          const isActive = tab.key === activeModule.key
          return (
            <Link
              key={tab.key}
              href={tab.href}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition-colors",
                isActive
                  ? "border-foreground bg-foreground text-background"
                  : "border-border bg-card text-muted-foreground hover:text-foreground",
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
