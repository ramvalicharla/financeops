"use client"

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface ContextBarBaseProps {
  children: ReactNode
  className?: string
}

export function ContextBarBase({ children, className }: ContextBarBaseProps) {
  return (
    <div className={cn("border-b border-border bg-card/70 px-4 py-3 md:px-6", className)}>
      {children}
    </div>
  )
}
