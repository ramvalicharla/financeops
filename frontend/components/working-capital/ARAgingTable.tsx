"use client"

import { cn, formatINR } from "@/lib/utils"
import type { WCARItem } from "@/lib/types/working-capital"

interface ARAgingTableProps {
  rows: WCARItem[]
}

const probabilityClass = (value: string | null): string => {
  const parsed = value ? Number.parseFloat(value) : 0
  if (parsed > 0.7) return "bg-emerald-500/20 text-emerald-300"
  if (parsed >= 0.4) return "bg-amber-500/20 text-amber-300"
  return "bg-red-500/20 text-red-300"
}

export function ARAgingTable({ rows }: ARAgingTableProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Top Overdue AR</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2">Customer</th>
              <th className="py-2">Amount</th>
              <th className="py-2">Days Overdue</th>
              <th className="py-2">Probability</th>
              <th className="py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-border/50">
                <td className="py-2 text-foreground">{row.customer_name}</td>
                <td className="py-2 text-muted-foreground">{formatINR(row.amount)}</td>
                <td className="py-2 text-muted-foreground">{row.days_overdue}</td>
                <td className="py-2">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs", probabilityClass(row.payment_probability_score))}>
                    {row.payment_probability_score ?? "0.0000"}
                  </span>
                </td>
                <td className="py-2 text-muted-foreground">Placeholder</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
