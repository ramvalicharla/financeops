"use client"

import { cn } from "@/lib/utils"

interface PolicyViolationBadgeProps {
  violation_type: string | null
  is_hard_block: boolean
  message?: string
}

export function PolicyViolationBadge({ violation_type, is_hard_block, message }: PolicyViolationBadgeProps) {
  if (!violation_type || violation_type === "none") {
    return null
  }

  return (
    <span
      title={message ?? violation_type}
      className={cn(
        "inline-flex rounded-full px-2 py-1 text-xs",
        is_hard_block
          ? "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
          : "bg-amber-500/20 text-amber-300",
      )}
    >
      {violation_type}
    </span>
  )
}
