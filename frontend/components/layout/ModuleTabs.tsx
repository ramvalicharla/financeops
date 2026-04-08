"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect } from "react"
import { CONTROL_PLANE_MODULE_TABS, resolveControlPlaneModule } from "@/lib/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { cn } from "@/lib/utils"

export function ModuleTabs() {
  const pathname = usePathname() ?? ""
  const setCurrentModule = useControlPlaneStore((state) => state.setCurrentModule)
  const activeModule = resolveControlPlaneModule(pathname)

  useEffect(() => {
    setCurrentModule(activeModule.label)
  }, [activeModule.label, setCurrentModule])

  return (
    <div className="border-b border-border bg-background/90 px-4 md:px-6">
      <nav aria-label="Module tabs" className="flex gap-2 overflow-x-auto py-3">
        {CONTROL_PLANE_MODULE_TABS.map((tab) => {
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
