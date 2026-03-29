"use client"

import { ArrowDownRight, ArrowUpRight } from "lucide-react"
import { cn, formatINR } from "@/lib/utils"

interface WCKPICardProps {
  label: string
  value: string
  unit: "days" | "₹"
  change: string
  change_direction: "up" | "down"
  is_good: boolean
}

export function WCKPICard({
  label,
  value,
  unit,
  change,
  change_direction,
  is_good,
}: WCKPICardProps) {
  const up = change_direction === "up"
  const chipGood = (up && is_good) || (!up && !is_good)

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-foreground">
        {unit === "₹" ? formatINR(value) : `${value} days`}
      </p>
      <div
        className={cn(
          "mt-3 inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs",
          chipGood
            ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
            : "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
        )}
      >
        {up ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
        {change}
      </div>
    </article>
  )
}
