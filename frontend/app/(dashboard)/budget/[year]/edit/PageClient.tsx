"use client"

import { useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { addBudgetLine, approveBudgetVersion, createBudgetVersion } from "@/lib/api/budget"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"

type EditableBudgetRow = {
  mis_line_item: string
  mis_category: string
  basis: string
  monthly_values: string[]
}

const monthLabels = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]

const defaultRows: EditableBudgetRow[] = [
  { mis_line_item: "Revenue", mis_category: "Revenue", basis: "", monthly_values: Array.from({ length: 12 }, () => "0.00") },
  { mis_line_item: "COGS", mis_category: "Cost of Revenue", basis: "", monthly_values: Array.from({ length: 12 }, () => "0.00") },
  { mis_line_item: "Operating Expenses", mis_category: "Operating Expenses", basis: "", monthly_values: Array.from({ length: 12 }, () => "0.00") },
  { mis_line_item: "EBITDA", mis_category: "EBITDA", basis: "", monthly_values: Array.from({ length: 12 }, () => "0.00") },
]

const asNumber = (value: string): number => {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export default function BudgetEditPage() {
  const router = useRouter()
  const params = useParams()
  const yearParam = Array.isArray(params?.year) ? params.year[0] : params?.year
  const year = Number.parseInt(yearParam ?? "", 10)
  const { fmt } = useFormattedAmount()
  const [rows, setRows] = useState<EditableBudgetRow[]>(defaultRows)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const annualTotals = useMemo(
    () =>
      rows.map((row) =>
        fmt(row.monthly_values.reduce((sum, value) => sum + asNumber(value), 0)),
      ),
    [rows],
  )

  const updateCell = (rowIndex: number, monthIndex: number, value: string) => {
    setRows((current) =>
      current.map((row, idx) =>
        idx === rowIndex
          ? {
              ...row,
              monthly_values: row.monthly_values.map((month, mIdx) =>
                mIdx === monthIndex ? value : month,
              ),
            }
          : row,
      ),
    )
  }

  const updateBasis = (rowIndex: number, value: string) => {
    setRows((current) =>
      current.map((row, idx) => (idx === rowIndex ? { ...row, basis: value } : row)),
    )
  }

  const persistBudget = async (submitForApproval: boolean) => {
    setSaving(true)
    setError(null)
    try {
      const version = await createBudgetVersion({
        fiscal_year: year,
        version_name: submitForApproval ? `Budget ${year} Submitted` : `Budget ${year} Draft`,
      })
      for (const row of rows) {
        await addBudgetLine(version.id, {
          mis_line_item: row.mis_line_item,
          mis_category: row.mis_category,
          monthly_values: row.monthly_values,
          basis: row.basis || undefined,
        })
      }
      if (submitForApproval) {
        await approveBudgetVersion(version.id)
      }
      router.push(`/budget/${year}`)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save budget")
    } finally {
      setSaving(false)
    }
  }

  if (!Number.isFinite(year)) {
    return <p className="text-sm text-[hsl(var(--brand-danger))]">Invalid year.</p>
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Edit Budget {year}</h1>
        <p className="text-sm text-muted-foreground">Spreadsheet-style monthly budget input.</p>
      </header>

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="min-w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Line Item</th>
              {monthLabels.map((month) => (
                <th key={month} className="px-3 py-2">
                  {month}
                </th>
              ))}
              <th className="px-3 py-2">Annual Total</th>
              <th className="px-3 py-2">Basis</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row.mis_line_item} className="border-b border-border/60">
                <td className="px-3 py-2">
                  <p className="font-medium text-foreground">{row.mis_line_item}</p>
                  <p className="text-xs text-muted-foreground">{row.mis_category}</p>
                </td>
                {row.monthly_values.map((value, monthIndex) => (
                  <td key={`${row.mis_line_item}-${monthIndex}`} className="px-3 py-2">
                    <input
                      value={value}
                      onChange={(event) => updateCell(rowIndex, monthIndex, event.target.value)}
                      className="w-20 rounded-md border border-border bg-background px-2 py-1 text-right"
                    />
                  </td>
                ))}
                <td className="px-3 py-2 text-right font-medium text-foreground">{annualTotals[rowIndex]}</td>
                <td className="px-3 py-2">
                  <input
                    value={row.basis}
                    onChange={(event) => updateBasis(rowIndex, event.target.value)}
                    className="w-56 rounded-md border border-border bg-background px-2 py-1"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={saving}
          onClick={() => persistBudget(false)}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Save as Draft
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={() => persistBudget(true)}
          className="rounded-md bg-[hsl(var(--brand-primary))] px-3 py-2 text-sm font-medium text-black"
        >
          Submit for Approval
        </button>
      </div>
    </div>
  )
}
