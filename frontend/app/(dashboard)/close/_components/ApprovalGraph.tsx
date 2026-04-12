"use client"

import { StateBadge } from "@/components/ui"
import { cn } from "@/lib/utils"

interface ApprovalGraphStage {
  id: string
  label: string
  status: string
  detail?: string | null
  completedAt?: string | null
}

interface ApprovalGraphProps {
  title: string
  description?: string
  stages: ApprovalGraphStage[]
  footerNote?: string
}

const normalize = (value: string): string => value.trim().toLowerCase().replace(/\s+/g, "_")

const toneClass = (status: string): string => {
  const normalized = normalize(status)
  if (["completed", "closed", "approved", "success", "pass", "hard_closed", "soft_closed"].includes(normalized)) {
    return "border-[hsl(var(--brand-success)/0.28)] bg-[hsl(var(--brand-success)/0.08)]"
  }
  if (["running", "in_progress", "pending", "queued", "open"].includes(normalized)) {
    return "border-[hsl(var(--brand-warning)/0.28)] bg-[hsl(var(--brand-warning)/0.08)]"
  }
  if (["blocked", "failed", "rejected", "error"].includes(normalized)) {
    return "border-[hsl(var(--brand-danger)/0.28)] bg-[hsl(var(--brand-danger)/0.08)]"
  }
  return "border-border bg-card"
}

export function ApprovalGraph({ title, description, stages, footerNote }: ApprovalGraphProps) {
  const completed = stages.filter((stage) =>
    ["completed", "closed", "approved", "success", "pass", "hard_closed", "soft_closed"].includes(
      normalize(stage.status),
    ),
  ).length
  const progress = stages.length ? Math.round((completed / stages.length) * 100) : 0

  return (
    <section className="rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Approval Graph</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">{title}</h2>
          {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Progress</p>
          <p className="mt-1 text-sm font-semibold text-foreground">{progress}%</p>
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="mt-5 space-y-3">
        {stages.map((stage, index) => {
          const isLast = index === stages.length - 1
          return (
            <div key={stage.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className={cn("mt-1 h-3 w-3 rounded-full border", toneClass(stage.status))} />
                {!isLast ? <span className="mt-2 min-h-10 w-px flex-1 bg-border" /> : null}
              </div>
              <div className={cn("flex-1 rounded-xl border p-3", toneClass(stage.status))}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{stage.label}</p>
                    {stage.detail ? <p className="mt-1 text-sm text-muted-foreground">{stage.detail}</p> : null}
                  </div>
                  <StateBadge status={stage.status} label={stage.status} />
                </div>
                {stage.completedAt ? (
                  <p className="mt-2 text-xs text-muted-foreground">Completed at {stage.completedAt}</p>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>

      {footerNote ? <p className="mt-4 text-xs text-muted-foreground">{footerNote}</p> : null}
    </section>
  )
}
