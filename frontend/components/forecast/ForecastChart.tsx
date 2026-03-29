"use client"

import {
  Bar,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { ForecastLineItem } from "@/lib/types/forecast"
import { decimalStringToNumber } from "@/lib/utils"

interface ForecastChartProps {
  lines: ForecastLineItem[]
  metric: string
  basePeriod: string
}

export function ForecastChart({ lines, metric, basePeriod }: ForecastChartProps) {
  const grouped = new Map<string, { period: string; actual: number; forecast: number }>()
  for (const row of lines) {
    if (row.mis_line_item !== metric) continue
    const existing = grouped.get(row.period) ?? { period: row.period, actual: 0, forecast: 0 }
    if (row.is_actual) {
      existing.actual = decimalStringToNumber(row.amount)
    } else {
      existing.forecast = decimalStringToNumber(row.amount)
    }
    grouped.set(row.period, existing)
  }
  const data = Array.from(grouped.values()).sort((a, b) => a.period.localeCompare(b.period))

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">Actual vs Forecast</h2>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <XAxis dataKey="period" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip />
            <Legend />
            <ReferenceLine x={basePeriod} strokeDasharray="4 4" stroke="#9CA3AF" />
            <Bar dataKey="actual" name="Actual" fill="#14B8A6" />
            <Line dataKey="forecast" name="Forecast" stroke="#F59E0B" strokeDasharray="6 4" strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}

