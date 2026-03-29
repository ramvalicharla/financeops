"use client"

import { cn, decimalStringToNumber } from "@/lib/utils"

interface VarianceBadgeProps {
  variance_pct: string
  is_revenue_line: boolean
}

export function VarianceBadge({ variance_pct, is_revenue_line }: VarianceBadgeProps) {
  const variance = decimalStringToNumber(variance_pct)
  const absolute = Math.abs(variance)
  const goodForRevenue = variance >= 0
  const goodForCost = variance <= 0
  const isGood = is_revenue_line ? goodForRevenue : goodForCost

  let tone = "text-[hsl(var(--brand-success))] bg-[hsl(var(--brand-success)/0.15)]"
  if (absolute > 15) {
    tone = "text-[hsl(var(--brand-danger))] bg-[hsl(var(--brand-danger)/0.15)]"
  } else if (absolute > 5) {
    tone = "text-amber-300 bg-amber-500/20"
  } else if (!isGood) {
    tone = "text-amber-300 bg-amber-500/20"
  }

  return (
    <span className={cn("inline-flex rounded-full px-2 py-1 text-xs font-medium", tone)}>
      {variance >= 0 ? "+" : ""}
      {variance.toFixed(2)}%
    </span>
  )
}

