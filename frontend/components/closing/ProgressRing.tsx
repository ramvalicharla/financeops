"use client"

import { useMemo } from "react"
import { cn } from "@/lib/utils"

interface ProgressRingProps {
  completed: number
  total: number
  size?: number
  className?: string
}

export function ProgressRing({ completed, total, size = 120, className }: ProgressRingProps) {
  const safeTotal = total > 0 ? total : 1
  const pct = Math.max(0, Math.min(100, (completed / safeTotal) * 100))
  const radius = (size - 10) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  const toneClass = useMemo(() => {
    if (pct > 80) return "stroke-[hsl(var(--brand-success))]"
    if (pct >= 40) return "stroke-amber-400"
    return "stroke-[hsl(var(--brand-danger))]"
  }, [pct])

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} data-testid="progress-ring">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth="10"
          className="fill-none stroke-muted"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth="10"
          strokeLinecap="round"
          style={{ strokeDasharray: circumference, strokeDashoffset: offset, transition: "stroke-dashoffset 350ms ease" }}
          className={cn("fill-none", toneClass)}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-xs uppercase tracking-wider text-muted-foreground">Progress</div>
        <div className="text-lg font-semibold text-foreground">{completed} / {total}</div>
      </div>
    </div>
  )
}
