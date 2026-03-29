"use client"

import { ORG_SETUP_STEP_NAMES } from "@/components/org-setup/constants"

interface StepIndicatorProps {
  step: number
}

export function StepIndicator({ step }: StepIndicatorProps) {
  const current = Math.min(Math.max(step, 1), 6)
  const progress = (current / 6) * 100

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card/70 p-4">
      <p className="text-sm text-muted-foreground">
        Step {current} of 6 - <span className="text-foreground">{ORG_SETUP_STEP_NAMES[current - 1]}</span>
      </p>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
