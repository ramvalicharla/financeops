"use client"

import type { ForecastLineItem } from "@/lib/types/forecast"
import { formatINR } from "@/lib/utils"

interface ForecastTableProps {
  lines: ForecastLineItem[]
}

export function ForecastTable({ lines }: ForecastTableProps) {
  const periods = Array.from(new Set(lines.map((row) => row.period))).sort()
  const lineItems = Array.from(new Set(lines.map((row) => row.mis_line_item)))
  const amountFor = (lineItem: string, period: string) => {
    const row = lines.find((item) => item.mis_line_item === lineItem && item.period === period && !item.is_actual)
    return row?.amount ?? "0.00"
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th className="px-3 py-2">Line Item</th>
            {periods.map((period) => (
              <th key={period} className="px-3 py-2">
                {period}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lineItems.map((lineItem) => (
            <tr key={lineItem} className="border-b border-border/50">
              <td className="px-3 py-2 font-medium text-foreground">{lineItem}</td>
              {periods.map((period) => {
                const isHistorical = lines.some(
                  (row) => row.mis_line_item === lineItem && row.period === period && row.is_actual,
                )
                return (
                  <td
                    key={`${lineItem}-${period}`}
                    className={`px-3 py-2 ${isHistorical ? "bg-muted/40 text-muted-foreground" : "text-foreground"}`}
                  >
                    {formatINR(amountFor(lineItem, period))}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

