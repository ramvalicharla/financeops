import type { ComplianceSummary } from "@/lib/types/compliance"

interface ComplianceProgressProps {
  summary: ComplianceSummary
}

export function ComplianceProgress({ summary }: ComplianceProgressProps) {
  const total = summary.total || 1
  const pct = Math.round((summary.green / total) * 100)
  const radius = 46
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-6">
        <svg width="120" height="120" viewBox="0 0 120 120" className="shrink-0">
          <circle cx="60" cy="60" r={radius} stroke="hsl(var(--muted))" strokeWidth="10" fill="transparent" />
          <circle
            cx="60"
            cy="60"
            r={radius}
            stroke="hsl(var(--brand-success))"
            strokeWidth="10"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
          />
          <text x="60" y="58" textAnchor="middle" className="fill-foreground text-lg font-semibold">
            {pct}%
          </text>
          <text x="60" y="76" textAnchor="middle" className="fill-muted-foreground text-[10px] uppercase tracking-[0.12em]">
            Green
          </text>
        </svg>
        <div className="space-y-1 text-sm text-muted-foreground">
          <p>Green: {summary.green}</p>
          <p>Amber: {summary.amber}</p>
          <p>Red: {summary.red}</p>
          <p>Grey: {summary.grey}</p>
          <p>Total: {summary.total}</p>
        </div>
      </div>
    </div>
  )
}

