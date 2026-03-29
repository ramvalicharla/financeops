"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { BudgetVsActualLine } from "@/lib/types/budget"
import { decimalStringToNumber } from "@/lib/utils"

interface BudgetVsActualChartProps {
  rows: BudgetVsActualLine[]
  metric: string
}

export function BudgetVsActualChart({ rows, metric }: BudgetVsActualChartProps) {
  const target = rows.find((row) => row.mis_line_item === metric) ?? rows[0]
  const data =
    target?.monthly.map((month) => ({
      month: month.month,
      budget: decimalStringToNumber(month.budget),
      actual: decimalStringToNumber(month.actual),
    })) ?? []

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">Budget vs Actual Trend</h2>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip />
            <Legend />
            <Bar dataKey="budget" fill="#60A5FA" radius={[4, 4, 0, 0]} />
            <Bar dataKey="actual" fill="#14B8A6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}

