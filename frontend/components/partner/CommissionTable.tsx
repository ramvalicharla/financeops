"use client"

import type { PartnerCommissionRow } from "@/lib/types/partner"

interface CommissionTableProps {
  commissions: PartnerCommissionRow[]
}

const statusClass: Record<PartnerCommissionRow["status"], string> = {
  pending: "border-amber-300/60 text-amber-200",
  approved: "border-blue-300/60 text-blue-200",
  paid: "border-emerald-300/50 text-emerald-200",
  cancelled: "border-[hsl(var(--brand-danger)/0.5)] text-[hsl(var(--brand-danger))]",
}

export function CommissionTable({ commissions }: CommissionTableProps) {
  const total = commissions.reduce((sum, row) => sum + Number.parseFloat(row.commission_amount), 0)

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Commission History</h2>
      </div>
      <div className="overflow-x-auto">
        <table aria-label="Commissions" className="min-w-full text-sm">
          <thead className="bg-background/50 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-3 text-left">Type</th>
              <th scope="col" className="px-4 py-3 text-left">Amount</th>
              <th scope="col" className="px-4 py-3 text-left">Rate</th>
              <th scope="col" className="px-4 py-3 text-left">Commission</th>
              <th scope="col" className="px-4 py-3 text-left">Status</th>
              <th scope="col" className="px-4 py-3 text-left">Period</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {commissions.map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-3 text-foreground">{row.commission_type}</td>
                <td className="px-4 py-3 text-muted-foreground">{row.payment_amount}</td>
                <td className="px-4 py-3 text-muted-foreground">{row.commission_rate}</td>
                <td className="px-4 py-3 text-foreground">{row.commission_amount}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full border px-2 py-0.5 text-xs ${statusClass[row.status]}`}>
                    {row.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{row.period ?? "-"}</td>
              </tr>
            ))}
            {commissions.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  No commissions yet.
                </td>
              </tr>
            ) : null}
          </tbody>
          <tfoot className="border-t border-border bg-background/30">
            <tr>
              <td className="px-4 py-3 font-medium text-foreground">Total</td>
              <td className="px-4 py-3 text-muted-foreground">-</td>
              <td className="px-4 py-3 text-muted-foreground">-</td>
              <td className="px-4 py-3 font-medium text-foreground">{total.toFixed(2)}</td>
              <td className="px-4 py-3 text-muted-foreground">-</td>
              <td className="px-4 py-3 text-muted-foreground">-</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  )
}
