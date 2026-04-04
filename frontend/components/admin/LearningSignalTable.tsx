"use client"

import type { LearningSignalSummary } from "@/lib/types/learning"

type LearningSignalTableProps = {
  signals: LearningSignalSummary[]
}

const shortTenant = (tenantId: string): string => {
  if (tenantId.length <= 12) return tenantId
  return `${tenantId.slice(0, 8)}...${tenantId.slice(-4)}`
}

export function LearningSignalTable({ signals }: LearningSignalTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table aria-label="Learning signals" className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Tenant</th>
            <th scope="col" className="px-3 py-2">Task Type</th>
            <th scope="col" className="px-3 py-2">Signal Type</th>
            <th scope="col" className="px-3 py-2">Model</th>
            <th scope="col" className="px-3 py-2">Tokens</th>
            <th scope="col" className="px-3 py-2">Date</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal) => (
            <tr key={signal.id} className="border-b border-border/50">
              <td className="px-3 py-2 text-muted-foreground">{shortTenant(signal.tenant_id)}</td>
              <td className="px-3 py-2 text-foreground">{signal.task_type}</td>
              <td className="px-3 py-2 text-muted-foreground">{signal.signal_type}</td>
              <td className="px-3 py-2 text-foreground">{signal.model_used}</td>
              <td className="px-3 py-2 text-muted-foreground">
                {signal.prompt_tokens + signal.completion_tokens}
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {new Date(signal.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
          {signals.length === 0 ? (
            <tr>
              <td className="px-3 py-3 text-muted-foreground" colSpan={6}>
                No recent learning signals available.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  )
}
