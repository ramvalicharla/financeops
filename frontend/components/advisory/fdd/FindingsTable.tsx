"use client"

import type { FDDFinding } from "@/lib/types/fdd"
import { formatINRCompact } from "@/lib/utils"

interface FindingsTableProps {
  findings: FDDFinding[]
}

const severityClass: Record<string, string> = {
  critical: "bg-[hsl(var(--brand-danger)/0.22)] text-[hsl(var(--brand-danger))]",
  high: "bg-orange-500/20 text-orange-300",
  medium: "bg-amber-500/20 text-amber-300",
  low: "bg-blue-500/20 text-blue-300",
  informational: "bg-muted text-muted-foreground",
}

export function FindingsTable({ findings }: FindingsTableProps) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Findings</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-background/80">
            <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
              <th className="px-4 py-2">Severity</th>
              <th className="px-4 py-2">Section</th>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">Financial Impact</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding) => (
              <tr key={finding.id} className="border-t border-border/60">
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${severityClass[finding.severity] ?? severityClass.informational}`}>
                    {finding.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{finding.finding_type}</td>
                <td className="px-4 py-3 text-foreground">{finding.title}</td>
                <td className="px-4 py-3 text-foreground">
                  {finding.financial_impact ? formatINRCompact(finding.financial_impact) : "-"}
                </td>
              </tr>
            ))}
            {findings.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-muted-foreground" colSpan={4}>
                  No findings generated yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
