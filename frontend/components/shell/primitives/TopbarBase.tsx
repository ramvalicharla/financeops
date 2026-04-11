"use client"

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface TopbarBaseProps {
  children: ReactNode
  className?: string
}

export function TopbarBase({ children, className }: TopbarBaseProps) {
  return (
    <header
      className={cn(
        "sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur",
        className,
      )}
    >
      {children}
    </header>
  )
}
