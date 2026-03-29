"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { type TaxPosition } from "@/lib/types/sprint11"

export type DeferredTaxScheduleProps = {
  positions: TaxPosition[]
}

export function DeferredTaxSchedule({ positions }: DeferredTaxScheduleProps) {
  const { fmt, scaleLabel } = useFormattedAmount()

  const net = positions.reduce((sum, row) => {
    const value = Number.parseFloat(row.deferred_tax_impact)
    if (Number.isNaN(value)) {
      return sum
    }
    return row.is_asset ? sum + value : sum - value
  }, 0)

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Deferred Tax Positions</p>
      <p className="mt-1 text-xs text-muted-foreground">{scaleLabel}</p>
      <table className="mt-3 w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Position</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Type</th>
            <th className="px-3 py-2 text-right text-xs text-muted-foreground">Temporary Difference</th>
            <th className="px-3 py-2 text-right text-xs text-muted-foreground">Deferred Impact</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((row) => (
            <tr
              key={row.id}
              className={`border-b border-border/60 last:border-0 ${
                row.is_asset ? "bg-emerald-500/5" : "bg-red-500/5"
              }`}
            >
              <td className="px-3 py-2 text-foreground">{row.position_name}</td>
              <td className="px-3 py-2">
                <span className={row.is_asset ? "text-emerald-400" : "text-red-400"}>
                  {row.is_asset ? "DTA" : "DTL"}
                </span>
              </td>
              <td className="px-3 py-2 text-right text-foreground">
                {fmt(row.temporary_difference)}
              </td>
              <td className="px-3 py-2 text-right text-foreground">
                {fmt(row.deferred_tax_impact)}
              </td>
            </tr>
          ))}
          <tr className="border-t border-border">
            <td className="px-3 py-2 font-semibold text-foreground" colSpan={3}>
              Net DTA / DTL
            </td>
            <td className={`px-3 py-2 text-right font-semibold ${net >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {fmt(net)}
            </td>
          </tr>
        </tbody>
      </table>
      {positions.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          No deferred tax positions configured for this tenant.
        </p>
      ) : null}
    </div>
  )
}
