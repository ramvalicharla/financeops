"use client"

import { formatINR } from "@/lib/utils"
import type { WCAPItem } from "@/lib/types/working-capital"

interface APAgingTableProps {
  rows: Array<WCAPItem & { saving_inr?: string }>
}

export function APAgingTable({ rows }: APAgingTableProps) {
  const filtered = rows.filter((row) => row.early_payment_discount_available)

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Discount Opportunities AP</h3>
      <div className="overflow-x-auto">
        <table aria-label="Accounts payable aging" className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th scope="col" className="py-2">Vendor</th>
              <th scope="col" className="py-2">Amount</th>
              <th scope="col" className="py-2">Days Overdue</th>
              <th scope="col" className="py-2">Discount %</th>
              <th scope="col" className="py-2">Saving ₹</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const pct = row.early_payment_discount_pct ?? "0"
              const saving = row.saving_inr ?? "0"
              return (
                <tr key={row.id} className="border-b border-border/50">
                  <td className="py-2 text-foreground">{row.vendor_name}</td>
                  <td className="py-2 text-muted-foreground">{formatINR(row.amount)}</td>
                  <td className="py-2 text-muted-foreground">{row.days_overdue}</td>
                  <td className="py-2 text-muted-foreground">{pct}</td>
                  <td className="py-2 text-muted-foreground">{formatINR(saving)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
