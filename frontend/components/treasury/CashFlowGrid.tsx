"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import {
  parseDisplayAmountToRaw,
  SCALE_DIVISORS,
} from "@/lib/utils"
import { type ForecastWeek } from "@/lib/types/sprint11"

export type CashFlowGridProps = {
  weeks: ForecastWeek[]
  onCellEdit?: (weekNumber: number, field: EditableField, value: string) => Promise<void>
}

export type EditableField =
  | "customer_collections"
  | "other_inflows"
  | "supplier_payments"
  | "payroll"
  | "rent_and_utilities"
  | "loan_repayments"
  | "tax_payments"
  | "capex"
  | "other_outflows"

type GridRow = {
  key:
    | EditableField
    | "total_inflows"
    | "total_outflows"
    | "net_cash_flow"
    | "closing_balance"
  label: string
  computed?: boolean
}

const rows: GridRow[] = [
  { key: "customer_collections", label: "Customer Collections" },
  { key: "other_inflows", label: "Other Inflows" },
  { key: "total_inflows", label: "Total Inflows", computed: true },
  { key: "supplier_payments", label: "Supplier Payments" },
  { key: "payroll", label: "Payroll" },
  { key: "rent_and_utilities", label: "Rent / Utilities" },
  { key: "loan_repayments", label: "Loan Repayments" },
  { key: "tax_payments", label: "Tax Payments" },
  { key: "capex", label: "CapEx" },
  { key: "other_outflows", label: "Other Outflows" },
  { key: "total_outflows", label: "Total Outflows", computed: true },
  { key: "net_cash_flow", label: "Net Cash Flow", computed: true },
  { key: "closing_balance", label: "Closing Balance", computed: true },
]

const editableFields: EditableField[] = [
  "customer_collections",
  "other_inflows",
  "supplier_payments",
  "payroll",
  "rent_and_utilities",
  "loan_repayments",
  "tax_payments",
  "capex",
  "other_outflows",
]

// formatNumeric is only used to revert an editable cell to a parseable string
// on blur when the user's input is invalid. fmtNum handles display formatting.
const formatNumeric = (value: string): string => {
  const amount = Number.parseFloat(value)
  return Number.isNaN(amount) ? value : String(amount)
}

export function CashFlowGrid({ weeks, onCellEdit }: CashFlowGridProps) {
  const { fmtNum, scaleLabel, scale } = useFormattedAmount()

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <div className="px-3 pt-2 text-xs text-muted-foreground">{scaleLabel}</div>
      <table aria-label="Cash flow" className="w-full min-w-[1300px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="px-3 py-2 text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">Line Item</th>
            {weeks.map((week) => (
              <th
                key={week.week_number}
                scope="col"
                className="px-3 py-2 text-right text-xs text-muted-foreground"
              >
                <div className="space-y-0.5">
                  <p>Week {week.week_number}</p>
                  <p className="text-[10px] opacity-80">{week.week_start_date}</p>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-foreground">{row.label}</td>
              {weeks.map((week) => {
                const value = week[row.key]
                const isNegativeClosing =
                  row.key === "closing_balance" && Number.parseFloat(value) < 0
                const isEditable = editableFields.includes(row.key as EditableField)
                return (
                  <td
                    key={`${week.week_number}-${row.key}`}
                    className={`px-3 py-2 text-right ${
                      row.computed ? "font-medium" : ""
                    } ${
                      isNegativeClosing
                        ? "bg-[hsl(var(--brand-danger)/0.15)] text-[hsl(var(--brand-danger))]"
                        : "text-foreground"
                    }`}
                  >
                    {isEditable ? (
                      <input
                        type="text"
                        defaultValue={fmtNum(value)}
                        onBlur={(event) => {
                          const next = event.currentTarget.value.trim()
                          if (!next || !onCellEdit) {
                            return
                          }
                          const parsedRaw = parseDisplayAmountToRaw(next, scale)
                          if (parsedRaw === null) {
                            event.currentTarget.value = formatNumeric(value)
                            return
                          }
                          const raw = parsedRaw.toFixed(2)
                          event.currentTarget.value = formatNumeric(
                            String(parsedRaw / SCALE_DIVISORS[scale]),
                          )
                          void onCellEdit(week.week_number, row.key as EditableField, raw)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.currentTarget.blur()
                          }
                        }}
                        className="w-24 rounded border border-border bg-background px-2 py-1 text-right text-xs text-foreground outline-none focus:border-[hsl(var(--brand-primary))]"
                      />
                    ) : (
                      fmtNum(value)
                    )}
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
