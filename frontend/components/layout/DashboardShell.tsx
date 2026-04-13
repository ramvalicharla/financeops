"use client"

import type { ReactNode } from "react"
import { useUIStore } from "@/lib/store/ui"
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
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed)

  return (
    <div
      className={cn(
        "flex h-full flex-col transition-all duration-200",
        sidebarCollapsed ? "md:pl-14" : "md:pl-60",
      )}
    >
      {children}
    </div>
  )
}
