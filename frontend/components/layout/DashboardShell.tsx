"use client"

import type { ReactNode } from "react"
import { useUIStore } from "@/lib/store/ui"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { cn } from "@/lib/utils"

interface DashboardShellProps {
  children: ReactNode
}

/**
 * Thin client wrapper that applies dynamic left-padding to match the sidebar
 * width (collapsed: pl-14 / expanded: pl-60). Kept as a separate component
 * because app/(dashboard)/layout.tsx is a Server Component.
 */
export function DashboardShell({ children }: DashboardShellProps) {
  const sidebarCollapsed = useWorkspaceStore((s) => s.sidebarCollapsed)
  const density = useUIStore((state) => state.density)

  return (
    <div
      className={cn(
        "flex h-full flex-col motion-safe:transition-all motion-safe:duration-200",
        sidebarCollapsed ? "md:pl-[52px]" : "md:pl-[220px]",
      )}
      data-density={density}
    >
      {children}
    </div>
  )
}
