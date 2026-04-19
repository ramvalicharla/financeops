"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"

interface StatRow {
  label: string
  value: string
}

interface Step5Props {
  flowSteps: FlowStripStep[]
  completionStats: StatRow[]
  completionStatuses: StatRow[]
  onBack: () => void
}

export function Step5Completion({ flowSteps, completionStats, completionStatuses, onBack }: Step5Props) {
  return (
    <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
      <FlowStrip
        title="Go-Live View"
        subtitle="This summary reads the current backend truth so the team can move into the control plane confidently."
        steps={flowSteps}
      />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Completion</h2>
        <p className="text-sm text-muted-foreground">
          Review the current backend-confirmed state, then continue into the governed workspaces.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {completionStats.map((stat) => (
          <article key={stat.label} className="rounded-3xl border border-border bg-background/80 p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{stat.label}</p>
            <p className="mt-3 text-lg font-semibold text-foreground">{stat.value}</p>
          </article>
        ))}
      </div>

      <section className="rounded-3xl border border-border bg-background/70 p-5">
        <h3 className="text-base font-semibold text-foreground">Backend confirmation</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {completionStatuses.map((status) => (
            <article key={status.label} className="rounded-2xl border border-border bg-card px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{status.label}</p>
              <p className="mt-2 text-sm text-foreground">{status.value}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="rounded-3xl border border-border bg-background/70 p-5">
        <h3 className="text-base font-semibold text-foreground">What to do next</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { href: "/settings/control-plane", label: "Open Control Plane" },
            { href: "/accounting/journals", label: "Review Journals" },
            { href: "/settings/airlock", label: "Inspect Airlock" },
            { href: "/reports", label: "Generate Reports" },
          ].map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-2xl border border-border bg-card px-4 py-4 text-sm text-foreground transition hover:border-[hsl(var(--brand-primary)/0.35)] hover:bg-[hsl(var(--brand-primary)/0.08)]"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" onClick={onBack}>← Back</Button>
        <Button asChild>
          <Link href="/settings/control-plane">Enter the Control Plane →</Link>
        </Button>
      </div>
    </section>
  )
}
