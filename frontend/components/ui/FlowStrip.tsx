"use client"

import { cn } from "@/lib/utils"

export interface FlowStripStep {
  label: string
  tone?: "default" | "active" | "success" | "warning"
}

interface FlowStripProps {
  title: string
  subtitle: string
  steps: FlowStripStep[]
  className?: string
}

const toneClasses: Record<NonNullable<FlowStripStep["tone"]>, string> = {
  default: "border-border bg-background text-muted-foreground",
  active: "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.14)] text-foreground",
  success: "border-[hsl(var(--brand-success)/0.45)] bg-[hsl(var(--brand-success)/0.14)] text-foreground",
  warning: "border-[hsl(var(--brand-warning)/0.45)] bg-[hsl(var(--brand-warning)/0.16)] text-foreground",
}

// Pure presentational renderer. Step meaning must come from backend-derived parent state.
export function FlowStrip({ title, subtitle, steps, className }: FlowStripProps) {
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-4", className)}>
      <div className="space-y-1">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {steps.map((step, index) => (
          <div key={`${step.label}-${index}`} className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium",
                toneClasses[step.tone ?? "default"],
              )}
            >
              {step.label}
            </span>
            {index < steps.length - 1 ? (
              <span className="text-xs text-muted-foreground" aria-hidden="true">
                {"->"}
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  )
}
