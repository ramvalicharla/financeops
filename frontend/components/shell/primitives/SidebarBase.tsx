"use client"

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface SidebarBaseProps {
  children: ReactNode
  className?: string
}

export function SidebarBase({ children, className }: SidebarBaseProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-card",
        className,
      )}
    >
      {children}
    </aside>
  )
}
