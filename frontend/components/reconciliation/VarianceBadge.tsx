"use client"

import { cn } from "@/lib/utils"

interface VarianceBadgeProps {
  status: "MATCHED" | "VARIANCE" | "MISSING_GL" | "MISSING_TB"
}

const statusConfig: Record<
  VarianceBadgeProps["status"],
  { label: string; className: string }
> = {
  MATCHED: {
    label: "✓ Matched",
    className: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  },
  VARIANCE: {
    label: "⚠ Variance",
    className: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
  },
  MISSING_GL: {
    label: "Missing in GL",
    className: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  },
  MISSING_TB: {
    label: "Missing in TB",
    className: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  },
}

export function VarianceBadge({ status }: VarianceBadgeProps) {
  const config = statusConfig[status]
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-1 text-xs font-medium",
        config.className,
      )}
    >
      {config.label}
    </span>
  )
}
