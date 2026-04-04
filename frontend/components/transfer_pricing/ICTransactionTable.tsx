"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { type ICTransaction } from "@/lib/types/sprint11"

export type ICTransactionTableProps = {
  rows: ICTransaction[]
}

export function ICTransactionTable({ rows }: ICTransactionTableProps) {
  const { fmt } = useFormattedAmount()

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table aria-label="Intercompany transactions" className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Party</th>
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Country</th>
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Type</th>
            <th scope="col" className="px-3 py-2 text-right text-xs text-muted-foreground">Amount (INR)</th>
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Method</th>
            <th scope="col" className="px-3 py-2 text-right text-xs text-muted-foreground">Adjustment</th>
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-foreground">{row.related_party_name}</td>
              <td className="px-3 py-2 text-foreground">{row.related_party_country}</td>
              <td className="px-3 py-2 text-foreground">{row.transaction_type}</td>
              <td className="px-3 py-2 text-right text-foreground">
                {fmt(row.transaction_amount_inr)}
              </td>
              <td className="px-3 py-2 text-foreground">{row.pricing_method}</td>
              <td
                className={`px-3 py-2 text-right ${
                  Number.parseFloat(row.adjustment_required) > 0
                    ? "text-amber-400"
                    : "text-foreground"
                }`}
              >
                {fmt(row.adjustment_required)}
              </td>
              <td className="px-3 py-2 text-foreground">
                {Number.parseFloat(row.adjustment_required) === 0 ? "No Adjustment" : "Adjustment Required"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
