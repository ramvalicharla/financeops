"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { type TaxProvisionRun } from "@/lib/types/sprint11"

export type TaxProvisionTableProps = {
  provision: TaxProvisionRun
}

export function TaxProvisionTable({ provision }: TaxProvisionTableProps) {
  const { fmt, fmtPct, scaleLabel } = useFormattedAmount()

  const rows: Array<{ label: string; value: string; emphasis?: boolean }> = [
    {
      label: "Accounting profit before tax",
      value: fmt(provision.accounting_profit_before_tax),
    },
    {
      label: "+ Permanent differences",
      value: fmt(provision.permanent_differences),
    },
    {
      label: "+ Timing differences",
      value: fmt(provision.timing_differences),
    },
    {
      label: "= Taxable income",
      value: fmt(provision.taxable_income),
      emphasis: true,
    },
    {
      label: "x Tax rate",
      value: fmtPct(provision.applicable_tax_rate),
    },
    {
      label: "= Current tax expense",
      value: fmt(provision.current_tax_expense),
      emphasis: true,
    },
    {
      label: "Deferred tax asset (DTA)",
      value: fmt(provision.deferred_tax_asset),
    },
    {
      label: "Deferred tax liability (DTL)",
      value: fmt(provision.deferred_tax_liability),
    },
    {
      label: "Net deferred tax",
      value: fmt(provision.net_deferred_tax),
      emphasis: true,
    },
    {
      label: "= Total tax expense",
      value: fmt(provision.total_tax_expense),
      emphasis: true,
    },
    {
      label: "Effective tax rate",
      value: fmtPct(provision.effective_tax_rate),
      emphasis: true,
    },
  ]

  return (
    <div className="rounded-xl border border-border bg-card">
      <table className="w-full text-sm">
        <caption className="pb-2 pl-3 text-left text-xs text-muted-foreground">
          {scaleLabel}
        </caption>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-muted-foreground">{row.label}</td>
              <td
                className={`px-3 py-2 text-right ${
                  row.emphasis ? "font-semibold text-foreground" : "font-medium text-foreground"
                }`}
              >
                {row.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
