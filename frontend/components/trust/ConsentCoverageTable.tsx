import type { ConsentSummary } from "@/lib/types/compliance"

interface ConsentCoverageTableProps {
  summary: ConsentSummary
}

export function ConsentCoverageTable({ summary }: ConsentCoverageTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th className="px-3 py-2">Consent Type</th>
            <th className="px-3 py-2">Granted</th>
            <th className="px-3 py-2">Withdrawn</th>
            <th className="px-3 py-2">Coverage</th>
          </tr>
        </thead>
        <tbody>
          {summary.consent.map((row) => {
            const pct = Number.parseFloat(row.coverage_pct) * 100
            return (
              <tr key={row.consent_type} className="border-b border-border/50">
                <td className="px-3 py-2">{row.consent_type}</td>
                <td className="px-3 py-2">{row.granted_count}</td>
                <td className="px-3 py-2">{row.withdrawn_count}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full bg-[hsl(var(--brand-primary))]"
                        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{pct.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

