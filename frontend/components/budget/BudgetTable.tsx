"use client"

import { useState } from "react"
import { Fragment } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import type { BudgetVsActualLine } from "@/lib/types/budget"
import { formatINR } from "@/lib/utils"
import { VarianceBadge } from "@/components/budget/VarianceBadge"

interface BudgetTableProps {
  rows: BudgetVsActualLine[]
}

export function BudgetTable({ rows }: BudgetTableProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const toggle = (lineItem: string) => {
    setExpanded((current) => ({ ...current, [lineItem]: !current[lineItem] }))
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.16em] text-muted-foreground">
          <tr>
            <th className="px-4 py-3">Line Item</th>
            <th className="px-4 py-3">Budget YTD</th>
            <th className="px-4 py-3">Actual YTD</th>
            <th className="px-4 py-3">Variance ₹</th>
            <th className="px-4 py-3">Variance %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <Fragment key={row.mis_line_item}>
              <tr className="border-b border-border/60">
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 font-medium text-foreground"
                    onClick={() => toggle(row.mis_line_item)}
                  >
                    {expanded[row.mis_line_item] ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                    {row.mis_line_item}
                  </button>
                  <p className="text-xs text-muted-foreground">{row.mis_category}</p>
                </td>
                <td className="px-4 py-3 text-foreground">{formatINR(row.budget_ytd)}</td>
                <td className="px-4 py-3 text-foreground">{formatINR(row.actual_ytd)}</td>
                <td className="px-4 py-3 text-foreground">{formatINR(row.variance_amount)}</td>
                <td className="px-4 py-3">
                  <VarianceBadge
                    variance_pct={row.variance_pct}
                    is_revenue_line={row.mis_category === "Revenue"}
                  />
                </td>
              </tr>
              {expanded[row.mis_line_item] ? (
                <tr className="border-b border-border/40 bg-muted/30">
                  <td colSpan={5} className="px-4 py-3">
                    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                      {row.monthly.map((month) => (
                        <article key={month.month} className="rounded-md border border-border bg-background px-3 py-2">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{month.month}</p>
                          <p className="text-xs text-foreground">Budget: {formatINR(month.budget)}</p>
                          <p className="text-xs text-foreground">Actual: {formatINR(month.actual)}</p>
                          <p className="text-xs text-muted-foreground">Variance: {formatINR(month.variance)}</p>
                        </article>
                      ))}
                    </div>
                  </td>
                </tr>
              ) : null}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
